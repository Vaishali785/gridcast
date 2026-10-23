"""Forecast accuracy metrics. Pure functions, independent of FastAPI and the frontend.

error = forecast - actual  (MW)
  bias > 0  => forecast over-predicted wind (on average)
  bias < 0  => forecast under-predicted wind (on average)
Only intervals with BOTH a valid forecast and a valid actual are used; NaN is never treated as 0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

HALF_HOUR_HOURS = 0.5


@dataclass(frozen=True)
class AccuracyMetrics:
    n_pairs: int
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None


def compute_metrics(forecast: pd.Series, actual: pd.Series) -> AccuracyMetrics:
    """MAE / RMSE / bias over index-aligned forecast & actual series."""
    f = pd.to_numeric(forecast, errors="coerce")
    a = pd.to_numeric(actual, errors="coerce")
    errors = (f - a).dropna().to_numpy(dtype=float)
    errors = errors[np.isfinite(errors)]
    n = int(errors.size)
    if n == 0:
        return AccuracyMetrics(0, None, None, None)
    return AccuracyMetrics(
        n_pairs=n,
        mae_mw=float(np.mean(np.abs(errors))),
        rmse_mw=float(math.sqrt(np.mean(errors**2))),
        bias_mw=float(np.mean(errors)),
    )


def mw_to_mwh(mw_values: pd.Series) -> float:
    """Energy from half-hourly average power: MWh = sum(MW) x 0.5 h."""
    return float(mw_values.dropna().sum() * HALF_HOUR_HOURS)


def error_histogram(errors: pd.Series, bin_width_mw: float = 1000.0) -> list[dict[str, float | int]]:
    """Signed-error histogram with fixed-width bins (labelled by bin lower edge)."""
    e = errors.dropna()
    if e.empty:
        return []
    lo = math.floor(e.min() / bin_width_mw) * bin_width_mw
    hi = math.floor(e.max() / bin_width_mw) * bin_width_mw + bin_width_mw
    edges = np.arange(lo, hi + bin_width_mw, bin_width_mw)
    counts, edges = np.histogram(e.to_numpy(), bins=edges)
    return [
        {"bin_start_mw": float(edges[i]), "bin_end_mw": float(edges[i + 1]), "count": int(counts[i])}
        for i in range(len(counts))
    ]
