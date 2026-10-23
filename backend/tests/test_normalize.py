import pandas as pd

from app.services.normalize import normalize_actuals, normalize_forecasts, resolve_actuals, resolve_conflicts
from tests.conftest import fc_df


def rec(fuel="WIND", gen=100, start="2026-01-10T12:00:00Z", pub="2026-01-10T12:35:00Z"):
    return {"dataset": "FUELHH", "publishTime": pub, "startTime": start, "settlementDate": "2026-01-10",
            "settlementPeriod": 25, "fuelType": fuel, "generation": gen}


def test_filters_wind_only_and_excludes_other_fuels():
    df, rep = normalize_actuals([rec("NUCLEAR", 4044), rec("WIND", 321), rec("CCGT", 9000)])
    assert list(df["generation"]) == [321.0]
    assert rep.rejected["excluded_non_wind_fuel"] == 2


def test_preserves_settlement_fields_and_publish_time():
    df, _ = normalize_actuals([rec()])
    row = df.iloc[0]
    assert row["settlement_period"] == 25 and row["settlement_date"] == "2026-01-10"
    assert row["publish_time"] == pd.Timestamp("2026-01-10T12:35:00Z")


def test_missing_values_are_rejected_not_zero():
    df, rep = normalize_actuals([rec(gen=None), rec(gen="abc"), rec(gen=float("inf")), rec(gen=0)])
    assert list(df["generation"]) == [0.0]            # genuine zero kept
    assert rep.rejected["missing_or_non_numeric_generation"] == 3


def test_rejects_bad_timestamps_negative_and_misaligned():
    df, rep = normalize_actuals([rec(start="garbage"), rec(start="2026-01-10T12:10:00Z"), rec(gen=-5)])
    assert df.empty
    assert rep.rejected == {"invalid_start_time": 1, "misaligned_start_time": 1, "negative_generation": 1}


def test_forecast_vintages_for_same_start_are_preserved():
    recs = [
        {"dataset": "WINDFOR", "publishTime": "2026-01-09T05:30:00Z", "startTime": "2026-01-10T12:00:00Z", "generation": 100},
        {"dataset": "WINDFOR", "publishTime": "2026-01-09T08:30:00Z", "startTime": "2026-01-10T12:00:00Z", "generation": 150},
    ]
    df, rep = normalize_forecasts(recs)
    assert len(df) == 2 and rep.exact_duplicates_dropped == 0


def test_exact_duplicates_dropped_conflicts_resolved_to_lowest_not_averaged():
    base = {"dataset": "WINDFOR", "publishTime": "2026-01-09T05:30:00Z", "startTime": "2026-01-10T12:00:00Z"}
    df, rep = normalize_forecasts([{**base, "generation": 100}, {**base, "generation": 100}, {**base, "generation": 140}])
    assert rep.exact_duplicates_dropped == 1 and len(df) == 2
    resolved, conflicts = resolve_conflicts(df, ["start_time", "publish_time"])
    assert conflicts == 1 and list(resolved["generation"]) == [100.0]      # not 120


def test_conflict_resolution_is_order_independent():
    a = fc_df([("2026-01-10T12:00:00Z", "2026-01-09T05:30:00Z", 140), ("2026-01-10T12:00:00Z", "2026-01-09T05:30:00Z", 100)])
    b = a.iloc[::-1].reset_index(drop=True)
    k = ["start_time", "publish_time"]
    assert resolve_conflicts(a, k)[0]["generation"].tolist() == resolve_conflicts(b, k)[0]["generation"].tolist() == [100.0]


def test_actuals_latest_publication_wins():
    df, _ = normalize_actuals([rec(gen=100, pub="2026-01-10T12:35:00Z"), rec(gen=110, pub="2026-01-10T13:35:00Z")])
    resolved, _ = resolve_actuals(df)
    assert len(resolved) == 1 and resolved["generation"].iloc[0] == 110


def test_empty_input():
    assert normalize_actuals([])[0].empty and normalize_forecasts([])[0].empty
