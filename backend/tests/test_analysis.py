from datetime import date

import pandas as pd
from app.models.domain import SelectionMode
from app.services.analysis import build_analysis, expected_intervals

from tests.conftest import fc_df, ts


def actuals(rows):
    return pd.DataFrame(
        [{"start_time": ts(s), "publish_time": ts(s), "generation": g} for s, g in rows]
    )


def test_expected_intervals_normal_and_dst_days():
    assert (
        len(expected_intervals(date(2026, 1, 10), date(2026, 1, 10), "Europe/London"))
        == 48
    )
    assert (
        len(expected_intervals(date(2026, 3, 29), date(2026, 3, 29), "Europe/London"))
        == 46
    )  # clocks forward
    assert (
        len(expected_intervals(date(2026, 10, 25), date(2026, 10, 25), "Europe/London"))
        == 50
    )  # clocks back


def test_alignment_missing_and_no_double_counting(rule):
    d = "2026-01-10T00:00:00Z"
    a = actuals([(d, 1000), ("2026-01-10T00:30:00Z", 2000)])  # 01:00 actual missing
    f = fc_df(
        [
            (d, "2026-01-09T08:30:00Z", 1100),
            (d, "2026-01-09T05:30:00Z", 5000),  # two vintages, one interval
            ("2026-01-10T01:00:00Z", "2026-01-09T08:30:00Z", 3000),
        ]
    )  # no actual
    res = build_analysis(
        a,
        f,
        date(2026, 1, 10),
        date(2026, 1, 10),
        SelectionMode.CUTOFF,
        rule,
        expand_hourly=False,
    )
    s = res.summary
    assert res.metrics.n_pairs == 1  # only 00:00 has both; 00:30 has no forecast
    assert res.metrics.bias_mw == 100.0  # latest eligible vintage (1100), not 5000
    assert (
        s["n_expected_intervals"] == 48
        and s["n_missing_actual"] == 46
        and s["n_missing_forecast"] == 46
    )
    assert s["n_forecast_available"] == 2 and s["n_actual_available"] == 2
    assert res.intervals["settlement_period"].iloc[:3].tolist() == [1, 2, 3]


def test_cutoff_mode_has_zero_lookahead_intervals(rule):
    d = "2026-01-10T00:00:00Z"
    f = fc_df([(d, "2026-01-09T08:30:00Z", 1), (d, "2026-01-09T19:30:00Z", 2)])
    res = build_analysis(
        actuals([(d, 1)]),
        f,
        date(2026, 1, 10),
        date(2026, 1, 10),
        SelectionMode.CUTOFF,
        rule,
        expand_hourly=False,
    )
    assert (
        res.summary["n_lookahead_intervals"] == 0
        and res.intervals["forecast_mw"].iloc[0] == 1
    )
    late = build_analysis(
        actuals([(d, 1)]),
        f,
        date(2026, 1, 10),
        date(2026, 1, 10),
        SelectionMode.LATEST,
        rule,
        expand_hourly=False,
    )
    assert (
        late.summary["n_lookahead_intervals"] == 1
        and late.intervals["forecast_mw"].iloc[0] == 2
    )


# --- WINDFOR is hourly, FUELHH is half-hourly -------------------------------------------------
def test_hourly_forecast_is_applied_to_both_half_hours_and_pairs_every_interval(rule):
    d, d30 = "2026-01-10T00:00:00Z", "2026-01-10T00:30:00Z"
    a = actuals([(d, 1000), (d30, 1200)])
    f = fc_df([(d, "2026-01-09T08:30:00Z", 1100)])  # hourly forecast, no :30 record
    res = build_analysis(
        a, f, date(2026, 1, 10), date(2026, 1, 10), SelectionMode.CUTOFF, rule
    )
    first_two = res.intervals.iloc[:2]
    assert first_two["forecast_mw"].tolist() == [1100, 1100]
    assert first_two["error_mw"].tolist() == [100, -100]
    assert (
        res.metrics.n_pairs == 2 and res.metrics.bias_mw == 0.0
    )  # each half-hour counted once
    assert res.summary["n_forecast_from_hourly"] == 1


def test_strict_mode_leaves_half_hours_without_a_matching_forecast_missing(rule):
    d = "2026-01-10T00:00:00Z"
    res = build_analysis(
        actuals([(d, 1000), ("2026-01-10T00:30:00Z", 1200)]),
        fc_df([(d, "2026-01-09T08:30:00Z", 1100)]),
        date(2026, 1, 10),
        date(2026, 1, 10),
        SelectionMode.CUTOFF,
        rule,
        expand_hourly=False,
    )
    assert res.metrics.n_pairs == 1 and res.summary["n_forecast_from_hourly"] == 0
    assert pd.isna(res.intervals["forecast_mw"].iloc[1])


def test_hourly_expansion_never_invents_a_forecast_for_an_hour_without_one(rule):
    res = build_analysis(
        actuals([("2026-01-10T05:00:00Z", 1), ("2026-01-10T05:30:00Z", 1)]),
        fc_df([("2026-01-10T00:00:00Z", "2026-01-09T08:30:00Z", 1100)]),
        date(2026, 1, 10),
        date(2026, 1, 10),
        SelectionMode.CUTOFF,
        rule,
    )
    five = res.intervals[
        res.intervals["start_time"].isin(
            [ts("2026-01-10T05:00:00Z"), ts("2026-01-10T05:30:00Z")]
        )
    ]
    assert five["forecast_mw"].isna().all()
