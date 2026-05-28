"""Unit tests for Portfolio state tracking and rebalancing."""

import pandas as pd
import pytest
from engine.portfolio import Portfolio
from engine.constants import CASH_YIELD_ANNUAL


def test_portfolio_initial_state():
    """Verify that a newly instantiated portfolio starts empty."""
    portfolio = Portfolio()
    assert portfolio.total_invested == 0.0
    assert portfolio.peak_value == 0.0
    assert portfolio.peak_value_per_dollar == 0.0
    assert len(portfolio.history) == 0
    
    # All share holdings should be initialized to zero
    for ticker, shares in portfolio.shares.items():
        assert shares == 0.0


def test_portfolio_value_calculation():
    """Verify that portfolio value is the sum of share values at market prices."""
    portfolio = Portfolio()
    portfolio.shares["QQQ"] = 10.0
    portfolio.shares["QLD"] = 5.0
    portfolio.shares["TQQQ"] = 2.0
    portfolio.shares["CASH"] = 100.0
    
    prices = {"QQQ": 150.0, "QLD": 80.0, "TQQQ": 40.0, "CASH": 1.0}
    
    # Expected value = (10 * 150) + (5 * 80) + (2 * 40) + (100 * 1)
    #                = 1500 + 400 + 80 + 100 = 2080 USD
    expected_value = 2080.0
    assert portfolio.get_value(prices) == expected_value
    
    # Verify allocations
    allocations = portfolio.get_allocation_pct(prices)
    assert allocations["QQQ"] == pytest.approx(1500.0 / 2080.0)
    assert allocations["QLD"] == pytest.approx(400.0 / 2080.0)
    assert allocations["TQQQ"] == pytest.approx(80.0 / 2080.0)
    assert allocations["CASH"] == pytest.approx(100.0 / 2080.0)


def test_portfolio_rebalance_and_contribution():
    """Verify that rebalancing allocates target weights perfectly including DCA cash."""
    portfolio = Portfolio()
    prices = {"QQQ": 100.0, "QLD": 50.0, "TQQQ": 25.0, "CASH": 1.0}
    
    # Rebalance from empty with a $1000 contribution
    target_alloc = {"QQQ": 0.5, "QLD": 0.3, "TQQQ": 0.2, "CASH": 0.0}
    portfolio.rebalance(target_alloc, prices, contribution=1000.0)
    
    assert portfolio.total_invested == 1000.0
    assert portfolio.get_value(prices) == 1000.0
    
    # Check allocated shares:
    # QQQ: $500 / 100 = 5 shares
    # QLD: $300 / 50 = 6 shares
    # TQQQ: $200 / 25 = 8 shares
    # CASH: $0
    assert portfolio.shares["QQQ"] == 5.0
    assert portfolio.shares["QLD"] == 6.0
    assert portfolio.shares["TQQQ"] == 8.0
    assert portfolio.shares["CASH"] == 0.0


def test_portfolio_drawdown():
    """Verify drawdown calculations work as expected absolute and per-dollar."""
    portfolio = Portfolio()
    prices = {"QQQ": 100.0, "QLD": 50.0, "TQQQ": 25.0, "CASH": 1.0}
    
    # Rebalance with $1000
    target_alloc = {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
    portfolio.rebalance(target_alloc, prices, contribution=1000.0)
    
    # QQQ drops by 20%
    crash_prices = {"QQQ": 80.0, "QLD": 50.0, "TQQQ": 25.0, "CASH": 1.0}
    
    # Absolute peak was 1000.0, current value is 800.0
    assert portfolio.get_value(crash_prices) == 800.0
    assert portfolio.get_drawdown_pct(crash_prices) == pytest.approx(20.0)
    assert portfolio.get_drawdown_pct_per_dollar(crash_prices) == pytest.approx(20.0)


def test_apply_cash_yield():
    """Verify interest yield increases CASH balances weekly."""
    portfolio = Portfolio()
    portfolio.shares["CASH"] = 1000.0
    
    portfolio.apply_cash_yield()
    
    # Cash interest is CASH * (1 + annual_yield/52)
    expected = 1000.0 * (1.0 + CASH_YIELD_ANNUAL / 52.0)
    assert portfolio.shares["CASH"] == pytest.approx(expected, 1e-6)
