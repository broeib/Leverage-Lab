"""Unit tests for strategies allocation validation and scaling."""

import pytest
from strategies.base import BaseStrategy
from strategies.sma_trend import SMATrendStrategy
from strategies.rsi_momentum import RSIMomentumStrategy
from strategies.vix_volatility import VIXVolatilityStrategy
from strategies.benchmarks import BuyHoldQQQ, EqualWeightStatic


def test_strategy_allocation_normalization():
    """Verify that allocation normalization handles scaling and validation errors."""
    # We can use a real strategy instance to test BaseStrategy.validate_allocation
    strategy = SMATrendStrategy()
    
    # Perfect weights
    good = {"QQQ": 0.5, "QLD": 0.5}
    norm = strategy.validate_allocation(good)
    assert norm["QQQ"] == 0.5
    assert norm["QLD"] == 0.5
    
    # Uneven weights should scale to sum to 1.0
    uneven = {"QQQ": 2.0, "QLD": 2.0}
    norm_uneven = strategy.validate_allocation(uneven)
    assert norm_uneven["QQQ"] == 0.5
    assert norm_uneven["QLD"] == 0.5
    
    # Negative weight should throw ValueError
    with pytest.raises(ValueError, match="Negative allocation"):
        strategy.validate_allocation({"QQQ": -0.1, "QLD": 1.1})
        
    # Invalid ticker should throw ValueError
    with pytest.raises(ValueError, match="Invalid ticker"):
        strategy.validate_allocation({"SPY": 1.0})
        
    # Zero allocation should throw ValueError
    with pytest.raises(ValueError, match="Total allocation is zero"):
        strategy.validate_allocation({"QQQ": 0.0, "QLD": 0.0})


def test_buy_and_hold_strategy():
    """Verify BuyAndHold strategy always returns full weight for target asset."""
    strategy = BuyHoldQQQ()
    assert strategy.name == "Buy & Hold QQQ (1x)"
    
    alloc = strategy.get_allocation(None, None, None)
    assert alloc == {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0}


def test_equal_weight_static():
    """Verify equal weighting returns static balanced allocations."""
    strategy = EqualWeightStatic()
    alloc = strategy.get_allocation(None, None, None)
    
    # Should equal 33.3% across QQQ, QLD, TQQQ
    assert alloc["QQQ"] == pytest.approx(0.33333, 1e-4)
    assert alloc["QLD"] == pytest.approx(0.33333, 1e-4)
    assert alloc["TQQQ"] == pytest.approx(0.33333, 1e-4)
