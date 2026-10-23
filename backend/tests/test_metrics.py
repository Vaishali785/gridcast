import math

import numpy as np
import pandas as pd

from app.services.metrics import compute_metrics, error_histogram, mw_to_mwh


def test_hand_calculated_metrics():
    # forecast - actual = [+100, -200, +300, 0]  -> |e| = 100,200,300,0
    f = pd.Series([1100, 800, 1300, 500.0]); a = pd.Series([1000, 1000, 1000, 500.0])
    m = compute_metrics(f, a)
    assert m.n_pairs == 4
    assert m.mae_mw == 150.0                                   # 600/4
    assert math.isclose(m.rmse_mw, math.sqrt((1e4 + 4e4 + 9e4) / 4))   # sqrt(35000)
    assert m.bias_mw == 50.0                                    # 200/4 -> over-forecast


def test_negative_bias_means_under_forecast():
    assert compute_metrics(pd.Series([90.0]), pd.Series([100.0])).bias_mw == -10.0


def test_missing_values_excluded_never_zero():
    f = pd.Series([100.0, np.nan, 300.0, 400.0]); a = pd.Series([90.0, 50.0, np.nan, 380.0])
    m = compute_metrics(f, a)
    assert m.n_pairs == 2 and m.mae_mw == 15.0 and m.bias_mw == 15.0   # errors +10, +20


def test_genuine_zero_actual_is_used():
    m = compute_metrics(pd.Series([100.0]), pd.Series([0.0]))
    assert m.n_pairs == 1 and m.mae_mw == 100.0


def test_no_pairs():
    m = compute_metrics(pd.Series([np.nan]), pd.Series([1.0]))
    assert (m.n_pairs, m.mae_mw, m.rmse_mw, m.bias_mw) == (0, None, None, None)


def test_energy_uses_half_hour_duration():
    assert mw_to_mwh(pd.Series([100.0, 200.0, np.nan])) == 150.0   # (100+200) x 0.5h


def test_histogram_counts_all_errors():
    h = error_histogram(pd.Series([-1500.0, -100.0, 50.0, 900.0, 2100.0]), 1000.0)
    assert sum(b["count"] for b in h) == 5
