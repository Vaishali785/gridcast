"""Forecast-vintage selection: the heart of the "no look-ahead" guarantee."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from app.core.errors import InvalidRequestError
from app.models.domain import CutoffRule, SelectionMode


def cutoff_for_date(delivery_date: date, rule: CutoffRule) -> pd.Timestamp:
    """UTC decision cutoff for a delivery (UK-local) date."""
    cutoff_date = delivery_date + pd.Timedelta(days=rule.day_offset)
    local = datetime.combine(cutoff_date, rule.local_time, tzinfo=rule.tz)
    return pd.Timestamp(local).tz_convert("UTC")


def cutoff_series(start_times: pd.Series, rule: CutoffRule) -> pd.Series:
    """Decision cutoff (UTC) for each delivery interval start time."""
    local_dates = start_times.dt.tz_convert(rule.tz).dt.date
    cache = {d: cutoff_for_date(d, rule) for d in local_dates.unique()}
    return local_dates.map(cache).astype("datetime64[ns, UTC]")


def _source_starts(
    starts: pd.Series, forecast_starts: pd.Series, expand_hourly: bool
) -> pd.Series:
    """Forecast `startTime` that serves each delivery interval.

    WINDFOR is published at HOURLY resolution while FUELHH actuals are half-hourly. A delivery
    interval uses a forecast with exactly its own startTime when one exists. Otherwise, a :30
    interval falls back to the forecast for the hour that contains it (the :00 start), so one hourly
    forecast value is applied to both half-hours of its hour. Never invents values: if the hour has
    no forecast the interval stays missing.
    """
    if not expand_hourly:
        return starts
    known = pd.Series(forecast_starts.unique())
    hour = starts.dt.floor("h")
    use_hour = ~starts.isin(known) & (starts != hour) & hour.isin(known)
    return starts.where(~use_hour, hour)


def select_forecasts(
    forecasts: pd.DataFrame,
    delivery_starts: pd.Series,
    mode: SelectionMode,
    rule: CutoffRule,
    as_of: pd.Timestamp | None = None,
    expand_hourly: bool = True,
) -> pd.DataFrame:
    """Pick one forecast vintage per delivery interval.

    `forecasts` must have one row per (start_time, publish_time) - see `resolve_conflicts`.

    CUTOFF  latest forecast with publish_time <= the interval's decision cutoff.
    VINTAGE latest forecast with publish_time <= `as_of`  (may include post-cutoff data).
    LATEST  latest forecast published at or before the delivery start (retrospective).

    Returns one row per delivery interval that HAS an eligible forecast, with columns:
    start_time, forecast_mw, forecast_publish_time, cutoff_time, lookahead (publish > cutoff),
    n_vintages_eligible, from_hourly (True when an hourly forecast was applied to a :30 interval).
    Intervals with no eligible forecast are absent (i.e. missing, not zero).
    """
    columns = [
        "start_time",
        "forecast_mw",
        "forecast_publish_time",
        "cutoff_time",
        "lookahead",
        "n_vintages_eligible",
        "from_hourly",
    ]
    if mode is SelectionMode.VINTAGE:
        if as_of is None:
            raise InvalidRequestError(
                "mode 'vintage' requires 'as_of' (forecast publication timestamp)"
            )
        if as_of.tzinfo is None:
            raise InvalidRequestError(
                "'as_of' must include a timezone offset, e.g. 2026-01-10T08:30:00Z"
            )

    starts = pd.Series(delivery_starts.unique(), name="start_time")
    if forecasts.empty or starts.empty:
        return pd.DataFrame(columns=columns)

    mapping = pd.DataFrame(
        {
            "start_time": starts,
            "source_start": _source_starts(
                starts, forecasts["start_time"], expand_hourly
            ),
        }
    )
    df = forecasts.rename(columns={"start_time": "source_start"}).merge(
        mapping, on="source_start", how="inner"
    )
    if df.empty:
        return pd.DataFrame(columns=columns)
    df["cutoff_time"] = cutoff_series(df["start_time"], rule)

    if mode is SelectionMode.CUTOFF:
        limit = df["cutoff_time"]
    elif mode is SelectionMode.VINTAGE:
        limit = pd.Series(as_of, index=df.index)
    else:  # LATEST
        limit = df["start_time"]
    df = df[df["publish_time"] <= limit]
    if df.empty:
        return pd.DataFrame(columns=columns)

    df = df.sort_values(["start_time", "publish_time"])
    n_eligible = df.groupby("start_time")["publish_time"].transform("count")
    chosen = df.assign(n_vintages_eligible=n_eligible).drop_duplicates(
        "start_time", keep="last"
    )
    chosen = chosen.rename(
        columns={"generation": "forecast_mw", "publish_time": "forecast_publish_time"}
    )
    chosen["lookahead"] = chosen["forecast_publish_time"] > chosen["cutoff_time"]
    chosen["from_hourly"] = chosen["source_start"] != chosen["start_time"]
    return chosen[columns].reset_index(drop=True)
