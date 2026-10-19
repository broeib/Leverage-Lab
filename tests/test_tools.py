"""Offline tests for the sweep and simulator tools."""

import pandas as pd

from tools.sweep_ema_channel import ParamEMAChannel, Variant, split_train_holdout
from tools.simulate_sma import map_allocation_to_label_and_reason


def test_split_train_holdout_slices_at_boundary():
    idx = pd.date_range("2018-12-21", periods=4, freq="W-FRI")
    h = pd.DataFrame({"total_value": [1.0, 2.0, 3.0, 4.0]}, index=idx)
    train, holdout = split_train_holdout(h, "2019-01-01")
    assert list(train.index) == list(idx[:2])
    assert list(holdout.index) == list(idx[2:])
    assert holdout.index.min() >= pd.Timestamp("2019-01-01")


def test_param_ema_channel_reset_clears_zone_memory():
    s = ParamEMAChannel(Variant(gray_mode="asym"))
    green = {"QQQ": 110.0, "EMA_TOP_200": 100.0, "EMA_BOT_200": 95.0}
    gray = {"QQQ": 97.0, "EMA_TOP_200": 100.0, "EMA_BOT_200": 95.0}
    s.get_allocation(None, green, {})
    assert s.get_allocation(None, gray, {})["QLD"] == 1.0  # gray entered from green
    s.reset()
    assert s.get_allocation(None, gray, {})["CASH"] == 1.0  # fresh run starts from red


def test_simulator_labels_match_strategy_allocations():
    cases = [
        ({"TQQQ": 1.0}, "TQQQ"),
        ({"QQQ": 0.5, "QLD": 0.5}, "QLD/QQQ"),
        ({"QLD": 1.0}, "QLD"),
        ({"QQQ": 1.0}, "QQQ"),
        ({"CASH": 1.0}, "CASH"),
    ]
    for alloc, label in cases:
        got, _ = map_allocation_to_label_and_reason(alloc, "BULL_STRONG", 50.0, 0.1, None)
        assert got == label
