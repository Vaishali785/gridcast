"""Builds the forecast-vs-actual analysis for a delivery-date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from app.models.domain import CutoffRule, SelectionMode
from app.services.metrics import (
    AccuracyMetrics,
    compute_metrics,
    error_histogram,
    mw_to_mwh,
)
from app.services.selection import cutoff_series, select_forecasts


@dataclass
class AnalysisResult:
    intervals: pd.DataFrame  # one row per expected delivery interval
    metrics: AccuracyMetrics
    summary: dict
    top_errors: pd.DataFrame
    histogram: list[dict]


def expected_intervals(start: date, end: date, tz_name: str) -> pd.DatetimeIndex:
    """All half-hour delivery starts (UTC) for local dates start..end inclusive.

    Local-day length follows DST (46/48/50 periods), so clock-change days are handled.
    """
    tz = ZoneInfo(tz_name)
    lo = pd.Timestamp(
        datetime.combine(start, datetime.min.time(), tzinfo=tz)
    ).tz_convert("UTC")
    hi = pd.Timestamp(
        datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    ).tz_convert("UTC")
    return pd.date_range(lo, hi, freq="30min", inclusive="left")


def build_analysis(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
    start: date,
    end: date,
    mode: SelectionMode,
    rule: CutoffRule,
    as_of: pd.Timestamp | None = None,
    top_n: int = 10,
    expand_hourly: bool = True,
) -> AnalysisResult:
    """`actuals` has one row per start_time; `forecasts` one row per (start_time, publish_time)."""
    idx = expected_intervals(start, end, rule.timezone)
    frame = pd.DataFrame({"start_time": idx})
    local = frame["start_time"].dt.tz_convert(rule.tz)
    local_midnight = local.dt.normalize()
    frame["settlement_date"] = local.dt.strftime("%Y-%m-%d")
    # period = half-hours elapsed since local midnight (real elapsed time, so DST-safe) + 1
    elapsed = frame["start_time"] - local_midnight.dt.tz_convert("UTC")
    frame["settlement_period"] = (elapsed / pd.Timedelta(minutes=30)).astype(int) + 1
    frame["cutoff_time"] = cutoff_series(frame["start_time"], rule)

    act = actuals[actuals["start_time"].isin(idx)][
        ["start_time", "generation", "publish_time"]
    ].rename(columns={"generation": "actual_mw", "publish_time": "actual_publish_time"})
    sel = select_forecasts(
        forecasts, frame["start_time"], mode, rule, as_of, expand_hourly
    ).drop(columns=["cutoff_time"])

    out = frame.merge(act, on="start_time", how="left").merge(
        sel, on="start_time", how="left"
    )
    out["lookahead"] = out["lookahead"].fillna(False).astype(bool)
    out["from_hourly"] = out["from_hourly"].fillna(False).astype(bool)
    out["error_mw"] = (
        out["forecast_mw"] - out["actual_mw"]
    )  # NaN if either side missing
    out["abs_error_mw"] = out["error_mw"].abs()
    out["n_vintages_eligible"] = out["n_vintages_eligible"].fillna(0).astype(int)

    paired = out.dropna(subset=["forecast_mw", "actual_mw"])
    metrics = compute_metrics(out["forecast_mw"], out["actual_mw"])
    has_f, has_a = out["forecast_mw"].notna(), out["actual_mw"].notna()

    summary = {
        "n_expected_intervals": int(len(out)),
        "n_forecast_available": int(has_f.sum()),
        "n_actual_available": int(has_a.sum()),
        "n_missing_forecast": int((~has_f).sum()),
        "n_missing_actual": int((~has_a).sum()),
        "n_missing_both": int((~has_f & ~has_a).sum()),
        "n_lookahead_intervals": int(out["lookahead"].sum()),
        "n_forecast_from_hourly": int(out["from_hourly"].sum()),
        # Averages are mean MW over intervals that have a value; energy is MWh (MW x 0.5 h).
        "forecast_mean_mw": _mean(out["forecast_mw"]),
        "forecast_peak_mw": _max(out["forecast_mw"]),
        "actual_mean_mw": _mean(out["actual_mw"]),
        "forecast_energy_mwh": mw_to_mwh(out["forecast_mw"]) if has_f.any() else None,
        "actual_energy_mwh": mw_to_mwh(out["actual_mw"]) if has_a.any() else None,
        # Like-for-like energy on paired intervals only (use this to compare forecast with actual).
        "paired_forecast_energy_mwh": mw_to_mwh(paired["forecast_mw"])
        if len(paired)
        else None,
        "paired_actual_energy_mwh": mw_to_mwh(paired["actual_mw"])
        if len(paired)
        else None,
    }
    top = paired.sort_values("abs_error_mw", ascending=False, kind="mergesort").head(
        top_n
    )
    return AnalysisResult(
        out, metrics, summary, top, error_histogram(paired["error_mw"])
    )


def _mean(s: pd.Series) -> float | None:
    s = s.dropna()
    return float(s.mean()) if len(s) else None


def _max(s: pd.Series) -> float | None:
    s = s.dropna()
    return float(s.max()) if len(s) else None
