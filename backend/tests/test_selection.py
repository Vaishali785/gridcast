import pandas as pd
import pytest

from app.core.errors import InvalidRequestError
from app.models.domain import SelectionMode
from app.services.selection import cutoff_for_date, select_forecasts
from tests.conftest import fc_df, ts

START = "2026-01-10T12:00:00Z"   # delivery date 2026-01-10 -> cutoff 2026-01-09 09:20 UTC (GMT in winter)


def pick(df, mode, rule, as_of=None):
    return select_forecasts(df, pd.Series([ts(START)]), mode, rule, as_of)


def test_cutoff_is_previous_day_0920_london(rule):
    assert cutoff_for_date(pd.Timestamp("2026-01-10").date(), rule) == ts("2026-01-09T09:20:00Z")


def test_cutoff_respects_bst(rule):
    # 2026-07-10 is BST (UTC+1): 09:20 London = 08:20 UTC
    assert cutoff_for_date(pd.Timestamp("2026-07-10").date(), rule) == ts("2026-07-09T08:20:00Z")


def test_selects_latest_forecast_at_or_before_cutoff(rule):
    df = fc_df([(START, "2026-01-09T05:30:00Z", 100), (START, "2026-01-09T08:30:00Z", 150),
                (START, "2026-01-09T10:30:00Z", 999)])   # after cutoff
    out = pick(df, SelectionMode.CUTOFF, rule)
    assert out["forecast_mw"].iloc[0] == 150 and not out["lookahead"].iloc[0]
    assert out["n_vintages_eligible"].iloc[0] == 2


def test_forecast_published_exactly_at_cutoff_is_eligible(rule):
    out = pick(fc_df([(START, "2026-01-09T09:20:00Z", 77)]), SelectionMode.CUTOFF, rule)
    assert out["forecast_mw"].iloc[0] == 77


def test_no_look_ahead_when_only_late_forecasts_exist(rule):
    out = pick(fc_df([(START, "2026-01-09T09:21:00Z", 500)]), SelectionMode.CUTOFF, rule)
    assert out.empty                                  # missing, not zero, not the late forecast


def test_latest_mode_uses_post_cutoff_forecast_and_flags_lookahead(rule):
    df = fc_df([(START, "2026-01-09T08:30:00Z", 150), (START, "2026-01-10T03:30:00Z", 180)])
    out = pick(df, SelectionMode.LATEST, rule)
    assert out["forecast_mw"].iloc[0] == 180 and bool(out["lookahead"].iloc[0])


def test_latest_mode_ignores_forecasts_published_after_delivery_start(rule):
    df = fc_df([(START, "2026-01-09T08:30:00Z", 150), (START, "2026-01-10T12:30:00Z", 999)])
    assert pick(df, SelectionMode.LATEST, rule)["forecast_mw"].iloc[0] == 150


def test_vintage_mode_flags_lookahead(rule):
    df = fc_df([(START, "2026-01-09T08:30:00Z", 150), (START, "2026-01-09T12:30:00Z", 170), (START, "2026-01-09T16:30:00Z", 190)])
    out = pick(df, SelectionMode.VINTAGE, rule, as_of=ts("2026-01-09T13:00:00Z"))
    assert out["forecast_mw"].iloc[0] == 170 and bool(out["lookahead"].iloc[0])
    early = pick(df, SelectionMode.VINTAGE, rule, as_of=ts("2026-01-09T09:00:00Z"))
    assert early["forecast_mw"].iloc[0] == 150 and not early["lookahead"].iloc[0]


def test_vintage_mode_requires_as_of(rule):
    with pytest.raises(InvalidRequestError):
        pick(fc_df([(START, "2026-01-09T08:30:00Z", 1)]), SelectionMode.VINTAGE, rule)


def test_each_interval_selected_independently(rule):
    s2 = "2026-01-11T00:00:00Z"   # cutoff 2026-01-10 09:20
    df = fc_df([(START, "2026-01-09T08:30:00Z", 150), (s2, "2026-01-09T08:30:00Z", 10), (s2, "2026-01-10T08:30:00Z", 20)])
    out = select_forecasts(df, pd.Series([ts(START), ts(s2)]), SelectionMode.CUTOFF, rule).set_index("start_time")
    assert out.loc[ts(START), "forecast_mw"] == 150 and out.loc[ts(s2), "forecast_mw"] == 20


def test_empty_forecasts(rule):
    empty = pd.DataFrame(columns=["start_time", "publish_time", "generation"])
    assert pick(empty, SelectionMode.CUTOFF, rule).empty
