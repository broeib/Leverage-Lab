"""Unit tests for Backtester engine with synthetic historical price data."""

import pytest
import pandas as pd
import numpy as np
from engine.backtester import Backtester
from strategies.base import BaseStrategy
from strategies.enhanced_sma import EnhancedSMATrendStrategy
from strategies.benchmarks import BuyHoldQQQ


def _create_synthetic_data(num_weeks=4):
    """Generate synthetic daily market data for testing."""
    # 4 weeks of Monday-Friday dates
    all_dates = []
    # Start on Monday 2023-01-02
    start = pd.Timestamp("2023-01-02")
    current = start
    while len(all_dates) < num_weeks * 5:
        if current.weekday() < 5:  # Mon-Fri
            all_dates.append(current)
        current += pd.Timedelta(days=1)

    index = pd.DatetimeIndex(all_dates)
    n = len(index)

    # Friday close is 100, Monday next bar is 105, etc.
    qqq = np.linspace(100.0, 150.0, n)
    qld = qqq * 0.8
    tqqq = qqq * 0.5

    close_prices = pd.DataFrame(
        {"QQQ": qqq, "QLD": qld, "TQQQ": tqqq},
        index=index,
    )
    vix_data = pd.DataFrame(
        {"VIX_Close": np.full(n, 20.0)},
        index=index,
    )
    indicator_data = pd.DataFrame(
        {
            "QQQ": qqq,
            "QLD": qld,
            "TQQQ": tqqq,
            "SMA_50": qqq * 0.95,
            "SMA_200": qqq * 0.90,
            "RSI": np.full(n, 55.0),
            "MACD": np.full(n, 1.0),
            "MACD_Signal": np.full(n, 0.5),
        },
        index=index,
    )
    rf_rate = pd.Series(np.full(n, 0.05), index=index, name="RF_RATE")

    return close_prices, vix_data, indicator_data, rf_rate


class AlwaysCashStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "Always Cash"

    @property
    def description(self) -> str:
        return "Always 100% Cash"

    def get_allocation(self, date, market_data: dict, portfolio_state: dict):
        return {"CASH": 1.0}


def test_next_day_execution_uses_next_day_prices():
    """Verify that execution_lag_days=1 executes trades on the next trading day prices."""
    close_prices, vix_data, indicator_data, rf_rate = _create_synthetic_data(num_weeks=4)

    # Weekly signal dates are the Fridays
    signal_dates = close_prices.index.to_series().groupby(close_prices.index.to_period("W")).last().tolist()
    expected_exec_date = close_prices.index[close_prices.index.get_loc(signal_dates[0]) + 1]

    # Different prices on signal date vs execution date
    signal_price = close_prices.loc[signal_dates[0], "QQQ"]
    exec_price = close_prices.loc[expected_exec_date, "QQQ"]
    assert signal_price != exec_price

    bt = Backtester(
        close_prices,
        vix_data,
        indicator_data,
        weekly_contribution=1000.0,
        rf_rate=rf_rate,
        slippage=0.0,
        execution_lag_days=1,
    )
    result = bt.run(BuyHoldQQQ())
    history = result.history

    # First recorded snapshot must be at the execution date (Monday), not signal date (Friday)
    assert history.index[0] == expected_exec_date

    # Shares purchased must equal contribution / exec_price
    expected_shares = 1000.0 / exec_price
    assert history["QQQ_shares"].iloc[0] == pytest.approx(expected_shares, rel=1e-4)


def test_lag_zero_reproduces_same_bar():
    """Verify that execution_lag_days=0 executes on signal date."""
    close_prices, vix_data, indicator_data, rf_rate = _create_synthetic_data(num_weeks=4)

    signal_dates = close_prices.index.to_series().groupby(close_prices.index.to_period("W")).last().tolist()
    signal_price = close_prices.loc[signal_dates[0], "QQQ"]

    bt = Backtester(
        close_prices,
        vix_data,
        indicator_data,
        weekly_contribution=1000.0,
        rf_rate=rf_rate,
        slippage=0.0,
        execution_lag_days=0,
    )
    result = bt.run(BuyHoldQQQ())
    history = result.history

    assert history.index[0] == signal_dates[0]
    expected_shares = 1000.0 / signal_price
    assert history["QQQ_shares"].iloc[0] == pytest.approx(expected_shares, rel=1e-4)


def test_slippage_reduces_final_value_and_twr():
    """Verify that slippage reduces final portfolio value and TWR unit."""
    close_prices, vix_data, indicator_data, rf_rate = _create_synthetic_data(num_weeks=4)

    bt_no_slip = Backtester(
        close_prices,
        vix_data,
        indicator_data,
        weekly_contribution=1000.0,
        rf_rate=rf_rate,
        slippage=0.0,
        execution_lag_days=1,
    )
    res_no_slip = bt_no_slip.run(BuyHoldQQQ())

    bt_slip = Backtester(
        close_prices,
        vix_data,
        indicator_data,
        weekly_contribution=1000.0,
        rf_rate=rf_rate,
        slippage=0.01,  # 1% slippage
        execution_lag_days=1,
    )
    res_slip = bt_slip.run(BuyHoldQQQ())

    final_val_no_slip = res_no_slip.history["total_value"].iloc[-1]
    final_val_slip = res_slip.history["total_value"].iloc[-1]
    assert final_val_slip < final_val_no_slip

    final_twr_no_slip = res_no_slip.history["twr_unit"].iloc[-1]
    final_twr_slip = res_slip.history["twr_unit"].iloc[-1]
    assert final_twr_slip < final_twr_no_slip


def test_cash_accrual_by_days_with_varying_rf():
    """Verify that cash accrues at rf_rate based on days elapsed between rebalances."""
    close_prices, vix_data, indicator_data, rf_rate = _create_synthetic_data(num_weeks=4)

    # First execution week rf = 0.05, second execution week rf = 0.10
    rf_varying = rf_rate.copy()
    midpoint = len(rf_varying) // 2
    rf_varying.iloc[midpoint:] = 0.10

    bt = Backtester(
        close_prices,
        vix_data,
        indicator_data,
        weekly_contribution=1000.0,
        rf_rate=rf_varying,
        slippage=0.0,
        execution_lag_days=0,
    )
    result = bt.run(AlwaysCashStrategy())
    h = result.history

    # Week 0: initial $1000 cash contributed
    assert h["CASH_value"].iloc[0] == pytest.approx(1000.0)

    # Week 1: $1000 accrued interest for elapsed days + $1000 new contribution
    days_elapsed = (h.index[1] - h.index[0]).days
    rf_used = h["rf_annual"].iloc[1]
    expected_cash_week1 = (1000.0 * (1.0 + rf_used * days_elapsed / 365.0)) + 1000.0
    assert h["CASH_value"].iloc[1] == pytest.approx(expected_cash_week1, rel=1e-5)


def test_reset_called_on_stateful_strategy():
    """Verify that strategy.reset() is called at the start of Backtester.run."""
    close_prices, vix_data, indicator_data, rf_rate = _create_synthetic_data(num_weeks=4)

    bt = Backtester(
        close_prices,
        vix_data,
        indicator_data,
        weekly_contribution=1000.0,
        rf_rate=rf_rate,
        slippage=0.0,
        execution_lag_days=1,
    )

    strategy = EnhancedSMATrendStrategy()
    res1 = bt.run(strategy)
    # Strategy internal state was modified during run
    res2 = bt.run(strategy)

    # Both consecutive runs must produce completely identical histories
    pd.testing.assert_frame_equal(res1.history, res2.history)


def test_nan_vix_becomes_none():
    """Verify that NaN VIX in vix_data maps to None in _get_market_data."""
    close_prices, vix_data, indicator_data, rf_rate = _create_synthetic_data(num_weeks=2)
    test_date = vix_data.index[0]
    vix_data.loc[test_date, "VIX_Close"] = np.nan

    bt = Backtester(
        close_prices,
        vix_data,
        indicator_data,
        weekly_contribution=1000.0,
        rf_rate=rf_rate,
        slippage=0.0,
        execution_lag_days=1,
    )

    data = bt._get_market_data(test_date)
    assert data["VIX"] is None
