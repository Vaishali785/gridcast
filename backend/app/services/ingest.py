"""Refresh pipeline: fetch -> validate -> persist -> report."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Literal

import pandas as pd

from app.core.config import Settings
from app.core.errors import UpstreamError
from app.services.elexon_client import FIXTURE_ACTUALS, FIXTURE_FORECASTS, ElexonClient, load_fixture
from app.services.normalize import normalize_actuals, normalize_forecasts, resolve_actuals, resolve_conflicts
from app.services.store import DataStore, utc_now_iso


def refresh_data(settings: Settings, store: DataStore, source: Literal["live", "fixture"] | None = None,
                 client: ElexonClient | None = None) -> dict:
    """Fetch and persist data for the configured window. Raises UpstreamError on failure,
    leaving previously stored data untouched."""
    source = source or settings.data_source
    window_start = pd.Timestamp(datetime.combine(settings.data_start_date, time.min, tzinfo=timezone.utc))
    window_end = pd.Timestamp(
        datetime.combine(settings.data_end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    )

    if source == "fixture":
        raw_actuals = load_fixture(settings.fixture_dir, FIXTURE_ACTUALS)
        raw_forecasts = load_fixture(settings.fixture_dir, FIXTURE_FORECASTS)
    else:
        own = client is None
        client = client or ElexonClient(settings)
        try:
            raw_actuals = client.fetch_actuals(settings.data_start_date, settings.data_end_date)
            publish_from = window_start.to_pydatetime() - timedelta(days=settings.forecast_publish_lookback_days)
            raw_forecasts = client.fetch_forecasts(publish_from, window_end.to_pydatetime())
        finally:
            if own:
                client.close()

    if not raw_actuals or not raw_forecasts:
        raise UpstreamError(
            "Elexon returned no records for the requested window; existing data was kept.",
            details={"actual_records": len(raw_actuals), "forecast_records": len(raw_forecasts)},
        )

    actuals, a_report = normalize_actuals(raw_actuals)
    forecasts, f_report = normalize_forecasts(raw_forecasts)
    in_window = lambda df: df[(df["start_time"] >= window_start) & (df["start_time"] < window_end)]  # noqa: E731
    actuals, forecasts = in_window(actuals), in_window(forecasts)

    _, actual_conflicts = resolve_actuals(actuals)
    _, forecast_conflicts = resolve_conflicts(forecasts, ["start_time", "publish_time"])

    meta = {
        "refreshed_at": utc_now_iso(),
        "source": source,
        "is_sample": source == "fixture",
        "window": [settings.data_start_date.isoformat(), settings.data_end_date.isoformat()],
        "actuals": {"raw_records": a_report.raw_records, "stored_records": len(actuals),
                    "rejected": a_report.rejected, "exact_duplicates_dropped": a_report.exact_duplicates_dropped,
                    "conflicting_keys": actual_conflicts},
        "forecasts": {"raw_records": f_report.raw_records, "stored_records": len(forecasts),
                      "rejected": f_report.rejected, "exact_duplicates_dropped": f_report.exact_duplicates_dropped,
                      "conflicting_keys": forecast_conflicts},
        "requests_made": len(client.request_log) if source == "live" and client else 0,
    }
    store.replace_all(actuals, forecasts, meta)
    return meta
