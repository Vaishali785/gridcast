"""Thin, defensive client for the Elexon Insights (BMRS) stream endpoints.

Verified against Elexon documentation:
  GET /datasets/WINDFOR/stream  - query: publishDateTimeFrom, publishDateTimeTo (date-time).
        Without publish filters the endpoint returns ONLY the latest forecast, so historical
        vintages must be requested through a publish-time window. Response: JSON array of
        {dataset, publishTime, startTime, generation}.
NOT independently verified (documentation pages are JS-rendered and the build sandbox had no
access to Elexon): the FUELHH stream's date filters. We use settlementDateFrom / settlementDateTo
(yyyy-MM-dd), which Elexon uses for settlement-date datasets. If the live API rejects them the
client raises UpstreamError with Elexon's response body - see README "Known limitations".
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from app.core.config import Settings
from app.core.errors import UpstreamError

log = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}


class ElexonClient:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.s = settings
        self._client = client or httpx.Client(
            base_url=settings.elexon_base_url, timeout=settings.elexon_timeout_seconds,
            headers={"Accept": "application/json"},
        )
        self._sleep = sleep
        self.request_log: list[dict[str, Any]] = []

    def close(self) -> None:
        self._client.close()

    # ---- low level ----------------------------------------------------------
    def _get_json(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        last_error = "unknown"
        for attempt in range(self.s.elexon_max_retries + 1):
            try:
                resp = self._client.get(path, params=params)
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
            except httpx.TransportError as exc:
                last_error = f"transport error: {exc}"
            else:
                if resp.status_code == 200:
                    self.request_log.append({"path": path, "params": params, "status": 200})
                    return self._extract_records(resp, path)
                if resp.status_code not in RETRY_STATUS:
                    raise UpstreamError(
                        f"Elexon returned HTTP {resp.status_code} for {path}",
                        details={"params": params, "status": resp.status_code, "body": resp.text[:500]},
                    )
                last_error = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    self._sleep(min(int(retry_after), 60))
                    continue
            if attempt < self.s.elexon_max_retries:
                self._sleep(min(2**attempt, 30))
        raise UpstreamError(
            f"Elexon request to {path} failed after {self.s.elexon_max_retries + 1} attempts ({last_error})",
            details={"params": params},
        )

    @staticmethod
    def _extract_records(resp: httpx.Response, path: str) -> list[dict[str, Any]]:
        try:
            payload = resp.json()
        except json.JSONDecodeError as exc:
            raise UpstreamError(f"Elexon returned non-JSON for {path}") from exc
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if not isinstance(payload, list):
            raise UpstreamError(f"Unexpected payload shape from {path}: {type(payload).__name__}")
        return payload

    # ---- datasets -----------------------------------------------------------
    def fetch_actuals(self, start: date, end: date, chunk_days: int = 7) -> list[dict[str, Any]]:
        """FUELHH records (all fuel types; WIND is filtered in normalisation) by settlement date."""
        out: list[dict[str, Any]] = []
        cur = start
        while cur <= end:
            hi = min(cur + timedelta(days=chunk_days - 1), end)
            out += self._get_json(
                "/datasets/FUELHH/stream",
                {"settlementDateFrom": cur.isoformat(), "settlementDateTo": hi.isoformat()},
            )
            cur = hi + timedelta(days=1)
        return out

    def fetch_forecasts(self, publish_from: datetime, publish_to: datetime, chunk_days: int = 3) -> list[dict[str, Any]]:
        """WINDFOR records for a publish-time window, in chunks (keeps all historical vintages)."""
        out: list[dict[str, Any]] = []
        cur = publish_from
        while cur < publish_to:
            hi = min(cur + timedelta(days=chunk_days), publish_to)
            out += self._get_json(
                "/datasets/WINDFOR/stream",
                {"publishDateTimeFrom": _z(cur), "publishDateTimeTo": _z(hi)},
            )
            cur = hi
        return out


def _z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- fixtures ----------------------------------------------------------------
FIXTURE_ACTUALS = "fuelhh_sample_2026-01.json"
FIXTURE_FORECASTS = "windfor_sample_2026-01.json"


def load_fixture(directory: Path, name: str) -> list[dict[str, Any]]:
    path = directory / name
    if not path.exists():
        raise UpstreamError(
            f"Fixture file not found: {path}. Run `python scripts/generate_sample_fixtures.py` "
            "or capture real responses with `python scripts/capture_fixtures.py`."
        )
    return json.loads(path.read_text())
