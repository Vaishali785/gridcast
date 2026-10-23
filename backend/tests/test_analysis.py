import pandas as pd

from app.models.domain import SelectionMode
from app.services.analysis import build_analysis, expected_intervals
from tests.conftest import fc_df, ts
from datetime import date


def actuals(rows):
    return pd.DataFrame([{"start_time": ts(s), "publish_time": ts(s), "generation": g} for s, g in rows])


def test_expected_intervals_normal_and_dst_days():
    assert len(expected_intervals(date(2026, 1, 10), date(2026, 1, 10), "Europe/London")) == 48
    assert len(expected_intervals(date(2026, 3, 29), date(2026, 3, 29), "Europe/London")) == 46   # clocks forward
    assert len(expected_intervals(date(2026, 10, 25), date(2026, 10, 25), "Europe/London")) == 50  # clocks back


def test_alignment_missing_and_no_double_counting(rule):
    d = "2026-01-10T00:00:00Z"
    a = actuals([(d, 1000), ("2026-01-10T00:30:00Z", 2000)])        # 01:00 actual missing
    f = fc_df([(d, "2026-01-09T08:30:00Z", 1100), (d, "2026-01-09T05:30:00Z", 5000),   # two vintages, one interval
               ("2026-01-10T01:00:00Z", "2026-01-09T08:30:00Z", 3000)])                # no actual
    res = build_analysis(a, f, date(2026, 1, 10), date(2026, 1, 10), SelectionMode.CUTOFF, rule)
    s = res.summary
    assert res.metrics.n_pairs == 1                          # only 00:00 has both; 00:30 has no forecast
    assert res.metrics.bias_mw == 100.0                      # latest eligible vintage (1100), not 5000
    assert s["n_expected_intervals"] == 48 and s["n_missing_actual"] == 46 and s["n_missing_forecast"] == 46
    assert s["n_forecast_available"] == 2 and s["n_actual_available"] == 2
    assert res.intervals["settlement_period"].iloc[:3].tolist() == [1, 2, 3]


def test_cutoff_mode_has_zero_lookahead_intervals(rule):
    d = "2026-01-10T00:00:00Z"
    f = fc_df([(d, "2026-01-09T08:30:00Z", 1), (d, "2026-01-09T19:30:00Z", 2)])
    res = build_analysis(actuals([(d, 1)]), f, date(2026, 1, 10), date(2026, 1, 10), SelectionMode.CUTOFF, rule)
    assert res.summary["n_lookahead_intervals"] == 0 and res.intervals["forecast_mw"].iloc[0] == 1
    late = build_analysis(actuals([(d, 1)]), f, date(2026, 1, 10), date(2026, 1, 10), SelectionMode.LATEST, rule)
    assert late.summary["n_lookahead_intervals"] == 1 and late.intervals["forecast_mw"].iloc[0] == 2
