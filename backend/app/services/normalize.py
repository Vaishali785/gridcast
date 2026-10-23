"""Validation and normalisation of raw Elexon records into clean DataFrames.

Rules (see README "Data assumptions"):
* all timestamps are parsed to timezone-aware UTC;
* delivery intervals must start on a :00 or :30 boundary;
* generation must be a finite, non-negative number - missing values are REJECTED, never zero;
* exact duplicate rows are dropped; rows sharing a key but disagreeing on value are kept
  here and resolved deterministically by `resolve_conflicts`.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.models.domain import IngestReport

WIND_FUEL_TYPE = "WIND"
ACTUAL_COLUMNS = ["start_time", "publish_time", "settlement_date", "settlement_period", "generation"]
FORECAST_COLUMNS = ["start_time", "publish_time", "generation"]


def _parse_utc(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce", format="ISO8601")


def _validate_common(df: pd.DataFrame) -> tuple[pd.DataFrame, Counter]:
    """Parse timestamps/generation and drop invalid rows, counting reasons."""
    rejected: Counter = Counter()
    df = df.copy()
    df["start_time"] = _parse_utc(df["startTime"])
    df["publish_time"] = _parse_utc(df["publishTime"])
    df["generation"] = pd.to_numeric(df["generation"], errors="coerce")

    bad_start = df["start_time"].isna()
    bad_pub = df["publish_time"].isna() & ~bad_start
    misaligned = ~bad_start & ~((df["start_time"].dt.minute.isin([0, 30])) & (df["start_time"].dt.second == 0))
    bad_gen = ~bad_start & ~bad_pub & ~misaligned & ~np.isfinite(df["generation"].astype("float64"))
    negative = ~bad_start & ~bad_pub & ~misaligned & ~bad_gen & (df["generation"] < 0)

    rejected["invalid_start_time"] = int(bad_start.sum())
    rejected["invalid_publish_time"] = int(bad_pub.sum())
    rejected["misaligned_start_time"] = int(misaligned.sum())
    rejected["missing_or_non_numeric_generation"] = int(bad_gen.sum())
    rejected["negative_generation"] = int(negative.sum())

    keep = ~(bad_start | bad_pub | misaligned | bad_gen | negative)
    return df[keep], Counter({k: v for k, v in rejected.items() if v})


def normalize_actuals(records: Iterable[dict[str, Any]]) -> tuple[pd.DataFrame, IngestReport]:
    """FUELHH records -> WIND-only actuals. Other fuel types are excluded entirely."""
    rows = list(records)
    raw = len(rows)
    if not rows:
        return pd.DataFrame(columns=ACTUAL_COLUMNS), IngestReport(0, 0, {}, 0)

    df = pd.DataFrame(rows)
    for col in ("startTime", "publishTime", "generation", "fuelType", "settlementDate", "settlementPeriod"):
        if col not in df:
            df[col] = None

    is_wind = df["fuelType"].astype("string").str.strip().str.upper() == WIND_FUEL_TYPE
    non_wind = int((~is_wind).sum())
    df = df[is_wind]

    df, rejected = _validate_common(df)
    if non_wind:
        rejected["excluded_non_wind_fuel"] = non_wind  # informational, not an error

    df = df.assign(
        settlement_date=df["settlementDate"].astype("string"),
        settlement_period=pd.to_numeric(df["settlementPeriod"], errors="coerce").astype("Int64"),
    )[ACTUAL_COLUMNS]
    before = len(df)
    df = df.drop_duplicates().sort_values(["start_time", "publish_time"]).reset_index(drop=True)
    return df, IngestReport(raw, len(df), dict(rejected), before - len(df))


def normalize_forecasts(records: Iterable[dict[str, Any]]) -> tuple[pd.DataFrame, IngestReport]:
    """WINDFOR records -> clean forecast vintages. Never deduplicates by startTime alone."""
    rows = list(records)
    raw = len(rows)
    if not rows:
        return pd.DataFrame(columns=FORECAST_COLUMNS), IngestReport(0, 0, {}, 0)

    df = pd.DataFrame(rows)
    for col in ("startTime", "publishTime", "generation"):
        if col not in df:
            df[col] = None
    df, rejected = _validate_common(df)
    df = df[FORECAST_COLUMNS]
    before = len(df)
    # Only EXACT duplicates (same start, publish AND value) are dropped.
    df = df.drop_duplicates().sort_values(["start_time", "publish_time"]).reset_index(drop=True)
    return df, IngestReport(raw, len(df), dict(rejected), before - len(df))


def resolve_conflicts(df: pd.DataFrame, key: list[str]) -> tuple[pd.DataFrame, int]:
    """Collapse rows sharing `key` but with different generation values.

    Deterministic rule: keep the LOWEST generation value (independent of row order).
    Returns the resolved frame and the number of keys that had conflicting values.
    Conflicting values are never averaged.
    """
    if df.empty:
        return df, 0
    sizes = df.groupby(key)["generation"].nunique()
    conflicts = int((sizes > 1).sum())
    ordered = df.sort_values(key + ["generation"], kind="mergesort")
    resolved = ordered.drop_duplicates(subset=key, keep="first").reset_index(drop=True)
    return resolved, conflicts


def resolve_actuals(actuals: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """One actual per delivery interval: the most recently published record wins.

    FUELHH can be re-published; the latest publishTime is the best available measurement.
    Ties on publishTime with different values fall back to `resolve_conflicts`.
    """
    if actuals.empty:
        return actuals, 0
    resolved, conflicts = resolve_conflicts(actuals, ["start_time", "publish_time"])
    latest = resolved.sort_values(["start_time", "publish_time"]).drop_duplicates("start_time", keep="last")
    return latest.reset_index(drop=True), conflicts
