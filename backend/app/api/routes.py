"""HTTP routes. Thin: validation + serialisation only; logic lives in services/."""
from __future__ import annotations

import threading
from datetime import date, datetime, time

import pandas as pd
from fastapi import APIRouter, Depends, Query, Request

from app.core.config import Settings, get_settings
from app.core.errors import DataNotLoadedError, GridCastError, InvalidRequestError
from app.models.domain import CutoffRule, SelectionMode
from app.schemas import api as S
from app.services.analysis import build_analysis, expected_intervals
from app.services.ingest import refresh_data
from app.services.repository import Repository, Snapshot
from app.services.selection import cutoff_for_date, cutoff_series

router = APIRouter(prefix="/api")
_refresh_lock = threading.Lock()

MODE_LABELS = {
    SelectionMode.CUTOFF: "Decision-time forecast (latest published at or before the decision cutoff)",
    SelectionMode.LATEST: "Retrospective: latest published forecast (NOT available at decision time)",
    SelectionMode.VINTAGE: "Selected forecast vintage (latest published at or before the chosen time)",
}
RATIONALE = (
    "GB day-ahead auctions close on D-1: EPEX SPOT GB 60-minute auction gate closure is 09:20 UK time "
    "(Nord Pool N2EX closes at 09:50). The earlier, 09:20, is used so that no forecast the buyer could not "
    "have seen is used. Configurable via DECISION_CUTOFF_* settings or the cutoff_time query parameter."
)


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


def _rule(settings: Settings, override: str | None = None) -> CutoffRule:
    t = settings.decision_cutoff_local_time
    if override:
        try:
            t = time.fromisoformat(override)
        except ValueError as exc:
            raise InvalidRequestError("cutoff_time must be HH:MM (24h, local market time)") from exc
    return CutoffRule(t, settings.decision_cutoff_timezone, settings.decision_cutoff_day_offset)


def _assumption(rule: CutoffRule) -> S.CutoffAssumption:
    return S.CutoffAssumption(description=rule.describe(), local_time=rule.local_time.strftime("%H:%M"),
                              timezone=rule.timezone, day_offset=rule.day_offset, rationale=RATIONALE)


def _snapshot(repo: Repository) -> Snapshot:
    snap = repo.snapshot()
    if snap is None:
        raise DataNotLoadedError("No data loaded yet. Call POST /api/data/refresh first.")
    return snap


def _check_range(settings: Settings, start: date, end: date) -> None:
    if start > end:
        raise InvalidRequestError("start_date must be on or before end_date")
    if start < settings.data_start_date or end > settings.data_end_date:
        raise InvalidRequestError(
            f"Dates must lie within the loaded window {settings.data_start_date}..{settings.data_end_date}")


def _rows(df: pd.DataFrame) -> list[dict]:
    cleaned = df.astype(object).where(df.notna(), None)
    return cleaned.to_dict("records")


def _ingest_stats(m: dict) -> S.IngestStats:
    return S.IngestStats(**m)


@router.get("/health", response_model=S.HealthResponse, tags=["system"])
def health(repo: Repository = Depends(get_repo)):
    return S.HealthResponse(status="ok", data_loaded=repo.store.refresh_meta() is not None)


@router.get("/metadata", response_model=S.MetadataResponse, tags=["system"])
def metadata(repo: Repository = Depends(get_repo), settings: Settings = Depends(get_settings)):
    rule = _rule(settings)
    base = dict(data_source=settings.data_source, window_start=settings.data_start_date,
                window_end=settings.data_end_date, cutoff=_assumption(rule))
    snap = repo.snapshot()
    if snap is None:
        return S.MetadataResponse(data_loaded=False, is_sample_data=settings.data_source == "fixture",
                                  last_successful_refresh=None, **base)
    m = snap.meta
    exp = expected_intervals(settings.data_start_date, settings.data_end_date, rule.timezone)
    pubs = snap.forecasts["publish_time"]
    cov = S.Coverage(
        expected_intervals=len(exp),
        actual_intervals=int(snap.actuals["start_time"].isin(exp).sum()),
        forecast_intervals=int(snap.forecasts["start_time"].drop_duplicates().isin(exp).sum()),
        first_publish_time=pubs.min() if len(pubs) else None, last_publish_time=pubs.max() if len(pubs) else None,
        distinct_publish_times=int(pubs.nunique()))
    base["data_source"] = m["source"]
    return S.MetadataResponse(data_loaded=True, is_sample_data=m["is_sample"],
                              last_successful_refresh=m["refreshed_at"], actuals=_ingest_stats(m["actuals"]),
                              forecasts=_ingest_stats(m["forecasts"]), coverage=cov, **base)


@router.get("/wind/actuals", response_model=S.ActualsResponse, tags=["wind"])
def actuals(start_date: date, end_date: date, repo: Repository = Depends(get_repo),
            settings: Settings = Depends(get_settings)):
    """Resolved WIND actuals (MW) for delivery dates in range. Missing intervals are omitted, never zero."""
    _check_range(settings, start_date, end_date)
    snap = _snapshot(repo)
    idx = expected_intervals(start_date, end_date, settings.decision_cutoff_timezone)
    df = snap.actuals[snap.actuals["start_time"].isin(idx)]
    recs = [S.ActualRecord(start_time=r["start_time"], publish_time=r["publish_time"],
                           settlement_date=r["settlement_date"], settlement_period=r["settlement_period"],
                           generation_mw=r["generation"]) for r in _rows(df)]
    return S.ActualsResponse(count=len(recs), records=recs)


@router.get("/wind/forecasts", response_model=S.ForecastsResponse, tags=["wind"])
def forecasts(start_date: date, end_date: date, limit: int = Query(5000, ge=1, le=50000),
              repo: Repository = Depends(get_repo), settings: Settings = Depends(get_settings)):
    """ALL forecast vintages (one record per startTime x publishTime) for delivery dates in range."""
    _check_range(settings, start_date, end_date)
    snap = _snapshot(repo)
    rule = _rule(settings)
    idx = expected_intervals(start_date, end_date, rule.timezone)
    df = snap.forecasts[snap.forecasts["start_time"].isin(idx)].copy()
    df["cutoff"] = cutoff_series(df["start_time"], rule) if len(df) else pd.NaT
    total = len(df)
    df = df.head(limit)
    recs = [S.ForecastRecord(start_time=r["start_time"], publish_time=r["publish_time"], generation_mw=r["generation"],
                             available_at_cutoff=r["publish_time"] <= r["cutoff"]) for r in _rows(df)]
    return S.ForecastsResponse(count=total, truncated=total > limit, records=recs)


@router.get("/wind/analysis", response_model=S.AnalysisResponse, tags=["wind"],
            responses={409: {"model": S.ErrorResponse}, 422: {"model": S.ErrorResponse}})
def analysis(start_date: date, end_date: date, mode: SelectionMode = SelectionMode.CUTOFF,
             as_of: datetime | None = Query(None, description="Required for mode=vintage (timezone-aware)."),
             cutoff_time: str | None = Query(None, description="Override local cutoff, HH:MM."),
             repo: Repository = Depends(get_repo), settings: Settings = Depends(get_settings)):
    _check_range(settings, start_date, end_date)
    rule = _rule(settings, cutoff_time)
    snap = _snapshot(repo)
    ts = pd.Timestamp(as_of) if as_of else None
    if mode is SelectionMode.VINTAGE and (ts is None or ts.tzinfo is None):
        raise InvalidRequestError("mode=vintage requires a timezone-aware 'as_of' (e.g. 2026-01-10T08:30:00Z)")
    res = build_analysis(snap.actuals, snap.forecasts, start_date, end_date, mode, rule, ts)
    m = res.metrics
    return S.AnalysisResponse(
        start_date=start_date, end_date=end_date, mode=mode.value, mode_label=MODE_LABELS[mode],
        is_retrospective=res.summary["n_lookahead_intervals"] > 0, as_of=ts, cutoff=_assumption(rule),
        is_sample_data=snap.meta["is_sample"], last_successful_refresh=snap.meta["refreshed_at"],
        summary=S.Summary(**res.summary),
        metrics=S.MetricsOut(n_pairs=m.n_pairs, mae_mw=m.mae_mw, rmse_mw=m.rmse_mw, bias_mw=m.bias_mw),
        series=[S.IntervalRow(**r) for r in _rows(res.intervals)],
        top_errors=[S.IntervalRow(**r) for r in _rows(res.top_errors)],
        error_histogram=[S.HistogramBin(**b) for b in res.histogram])


@router.get("/wind/vintage-times", response_model=S.VintageTimesResponse, tags=["wind"])
def vintage_times(start_date: date, end_date: date, repo: Repository = Depends(get_repo),
                  settings: Settings = Depends(get_settings)):
    """Distinct forecast publication times relevant to the range (for the vintage selector)."""
    _check_range(settings, start_date, end_date)
    snap = _snapshot(repo)
    idx = expected_intervals(start_date, end_date, settings.decision_cutoff_timezone)
    df = snap.forecasts[snap.forecasts["start_time"].isin(idx)]
    counts = df.groupby("publish_time")["start_time"].nunique().sort_index()
    return S.VintageTimesResponse(start_date=start_date, end_date=end_date,
                                  vintage_times=[S.VintageTime(publish_time=t, intervals_covered=int(n))
                                                 for t, n in counts.items()])


@router.get("/wind/vintages", response_model=S.VintageEvolution, tags=["wind"])
def vintages(start_time: datetime, repo: Repository = Depends(get_repo), settings: Settings = Depends(get_settings)):
    """How the forecast for ONE delivery interval evolved across publications."""
    if start_time.tzinfo is None:
        raise InvalidRequestError("start_time must be timezone-aware, e.g. 2026-01-10T12:00:00Z")
    snap = _snapshot(repo)
    rule = _rule(settings)
    st = pd.Timestamp(start_time).tz_convert("UTC")
    cutoff = cutoff_for_date(st.tz_convert(rule.tz).date(), rule)
    f = snap.forecasts[snap.forecasts["start_time"] == st].sort_values("publish_time")
    a = snap.actuals[snap.actuals["start_time"] == st]
    return S.VintageEvolution(
        start_time=st, cutoff_time=cutoff, actual_mw=float(a["generation"].iloc[0]) if len(a) else None,
        vintages=[S.VintageEntry(publish_time=r.publish_time, forecast_mw=float(r.generation),
                                 available_at_cutoff=bool(r.publish_time <= cutoff),
                                 hours_before_delivery=(st - r.publish_time).total_seconds() / 3600)
                  for r in f.itertuples()])


@router.post("/data/refresh", response_model=S.RefreshResponse, tags=["data"],
             responses={409: {"model": S.ErrorResponse}, 502: {"model": S.ErrorResponse}})
def refresh(body: S.RefreshRequest | None = None, repo: Repository = Depends(get_repo),
            settings: Settings = Depends(get_settings)):
    """Re-fetch data from Elexon (or fixtures). On failure previously stored data is kept."""
    if not _refresh_lock.acquire(blocking=False):
        raise GridCastError("A refresh is already in progress.")
    try:
        meta = refresh_data(settings, repo.store, body.source if body else None)
    finally:
        _refresh_lock.release()
    return S.RefreshResponse(refreshed_at=meta["refreshed_at"], source=meta["source"], is_sample=meta["is_sample"],
                             actuals=_ingest_stats(meta["actuals"]), forecasts=_ingest_stats(meta["forecasts"]))
