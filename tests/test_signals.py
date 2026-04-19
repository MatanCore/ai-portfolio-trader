import pandas as pd

from data.market_data import three_red_days
from signals.detector import evaluate_signals


def test_extreme_fear_trigger():
    r = evaluate_signals(fear_greed_value=5, vix_value=15, s5fi_value=60, spy_three_red=False)
    assert r.extreme_fear is True
    assert r.vix_spike is False
    assert r.active_count == 1


def test_no_signals():
    r = evaluate_signals(fear_greed_value=50, vix_value=14, s5fi_value=65, spy_three_red=False)
    assert r.active_count == 0


def test_all_signals():
    r = evaluate_signals(fear_greed_value=5, vix_value=35, s5fi_value=15, spy_three_red=True)
    assert r.extreme_fear and r.vix_spike and r.s5fi_breadth and r.three_red_days
    assert r.active_count == 4


def test_vix_edge():
    r = evaluate_signals(fear_greed_value=50, vix_value=30, s5fi_value=50, spy_three_red=False)
    assert r.vix_spike is False  # strict >30
    r2 = evaluate_signals(fear_greed_value=50, vix_value=30.01, s5fi_value=50, spy_three_red=False)
    assert r2.vix_spike is True


def test_missing_data_safe():
    r = evaluate_signals(fear_greed_value=None, vix_value=None, s5fi_value=None, spy_three_red=False)
    assert r.active_count == 0


def test_three_red_days_true():
    df = pd.DataFrame({"Close": [100.0, 99.0, 98.0, 97.0]})
    assert three_red_days(df) is True


def test_three_red_days_broken_by_green():
    df = pd.DataFrame({"Close": [100.0, 99.0, 100.5, 99.5]})
    assert three_red_days(df) is False


def test_three_red_days_insufficient_data():
    df = pd.DataFrame({"Close": [100.0, 99.0]})
    assert three_red_days(df) is False
