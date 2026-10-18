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


def test_spaxx_allocation_alias():
    """Verify that SPAXX in allocation dict is properly aliased to CASH."""
    strategy = SMATrendStrategy()
    alloc = {"SPAXX": 1.0}
    norm = strategy.validate_allocation(alloc)
    assert norm == {"CASH": 1.0}

    blended = {"QQQ": 0.5, "SPAXX": 0.5}
    norm_blended = strategy.validate_allocation(blended)
    assert norm_blended == {"QQQ": 0.5, "CASH": 0.5}


def test_graduated_leverage_regimes():
    """Verify 4-tier graduated leverage allocation across all market regimes."""
    from strategies.graduated_leverage import GraduatedLeverageStrategy
    import numpy as np

    strat = GraduatedLeverageStrategy(buffer_pct=0.0)

    # 1. Strong Bull: Price > 50 SMA AND Price > 200 SMA -> 100% TQQQ
    market_strong_bull = {"QQQ": 500.0, "SMA_50": 480.0, "SMA_200": 450.0}
    alloc1 = strat.get_allocation(None, market_strong_bull, {})
    assert alloc1 == {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}

    # 2. Bull Pullback: Price < 50 SMA BUT Price > 200 SMA -> 100% QLD
    market_pullback = {"QQQ": 470.0, "SMA_50": 480.0, "SMA_200": 450.0}
    alloc2 = strat.get_allocation(None, market_pullback, {})
    assert alloc2 == {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}

    # 3. Bottoming / Counter-Trend: Price > 50 SMA BUT Price < 200 SMA -> 100% QQQ
    market_counter = {"QQQ": 430.0, "SMA_50": 420.0, "SMA_200": 450.0}
    alloc3 = strat.get_allocation(None, market_counter, {})
    assert alloc3 == {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}

    # 4. Full Bear Market: Price < 50 SMA AND Price < 200 SMA -> 100% SPAXX (CASH)
    market_bear = {"QQQ": 400.0, "SMA_50": 420.0, "SMA_200": 450.0}
    alloc4 = strat.get_allocation(None, market_bear, {})
    assert alloc4 == {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

    # Fallback when indicators missing or NaN
    market_nan = {"QQQ": 400.0, "SMA_50": np.nan, "SMA_200": 450.0}
    alloc_nan = strat.get_allocation(None, market_nan, {})
    assert alloc_nan == {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


def test_buffered_graduated_leverage_anti_whipsaw():
    """Verify 1% buffer rule prevents premature whipsaw rebalancing."""
    from strategies.graduated_leverage import BufferedGraduatedLeverageStrategy

    strat = BufferedGraduatedLeverageStrategy(buffer_pct=0.01)

    # Initial state: Strong bull (QQQ > 50 and > 200 by a wide margin)
    alloc = strat.get_allocation(None, {"QQQ": 500.0, "SMA_50": 480.0, "SMA_200": 450.0}, {})
    assert alloc["TQQQ"] == 1.0

    # Price dips slightly below 50 SMA by only 0.5% (478 vs 480 -> -0.42%)
    # Under 1% buffer rule, price has NOT cleared below 50 SMA by 1.0%, so state remains ABOVE 50 SMA!
    alloc_dip = strat.get_allocation(None, {"QQQ": 478.0, "SMA_50": 480.0, "SMA_200": 450.0}, {})
    assert alloc_dip["TQQQ"] == 1.0  # Prevents whipsaw into QLD!

    # Price clearly drops below 50 SMA by > 1.0% (474 vs 480 -> -1.25%)
    # Now triggers transition to QLD (Bull Pullback)
    alloc_break = strat.get_allocation(None, {"QQQ": 474.0, "SMA_50": 480.0, "SMA_200": 450.0}, {})
    assert alloc_break["QLD"] == 1.0

    # Price bounces back up to 482 vs 480 (+0.42%), still within +1% buffer
    # Should maintain QLD until price firmly clears +1.0% above (i.e. > 484.8)
    alloc_bounce_chop = strat.get_allocation(None, {"QQQ": 482.0, "SMA_50": 480.0, "SMA_200": 450.0}, {})
    assert alloc_bounce_chop["QLD"] == 1.0

    # Price firmly clears 50 SMA by > 1.0% (486 vs 480)
    alloc_reclaim = strat.get_allocation(None, {"QQQ": 486.0, "SMA_50": 480.0, "SMA_200": 450.0}, {})
    assert alloc_reclaim["TQQQ"] == 1.0


def test_ema_channel_strategies():
    """Verify both EMA channel variants map the three channel states correctly."""
    from strategies.ema_channel import (
        EMAChannelAggressiveStrategy,
        EMAChannelConservativeStrategy,
    )

    aggressive = EMAChannelAggressiveStrategy()
    conservative = EMAChannelConservativeStrategy()

    green = {"QQQ": 110.0, "EMA_TOP": 105.0, "EMA_BOT": 100.0}
    gray = {"QQQ": 102.0, "EMA_TOP": 105.0, "EMA_BOT": 100.0}
    red = {"QQQ": 95.0, "EMA_TOP": 105.0, "EMA_BOT": 100.0}
    warmup = {"QQQ": 95.0, "EMA_TOP": None, "EMA_BOT": None}

    for strat in (aggressive, conservative):
        assert strat.get_allocation(None, green, {})["TQQQ"] == 1.0
        assert strat.get_allocation(None, red, {})["CASH"] == 1.0
        assert strat.get_allocation(None, warmup, {})["CASH"] == 1.0

    assert aggressive.get_allocation(None, gray, {})["QLD"] == 1.0
    assert conservative.get_allocation(None, gray, {})["QQQ"] == 1.0


def test_ema_channel_v2_overlay():
    """Verify v2 uses buffered channel lines and caps leverage at 1x when any risk trigger fires."""
    from strategies.ema_channel import EMAChannelV2Strategy

    s = EMAChannelV2Strategy()
    calm = {"ROLL_HIGH": 100.0, "EMA_FAST": 90.0, "RVOL": 15.0}

    # Clear green with no trigger -> 3x
    md = {"QQQ": 110.0, "EMA_TOP": 105.0, "EMA_BOT": 100.0, **calm}
    assert s.get_allocation(None, md, {})["TQQQ"] == 1.0

    # Just above the top line but inside the +1% buffer -> still gray -> 2x
    md = {"QQQ": 105.5, "EMA_TOP": 105.0, "EMA_BOT": 100.0, **calm}
    assert s.get_allocation(None, md, {})["QLD"] == 1.0

    # Just below the bottom line but inside the -1% buffer -> still gray -> 2x
    md = {"QQQ": 99.5, "EMA_TOP": 105.0, "EMA_BOT": 100.0, **calm}
    assert s.get_allocation(None, md, {})["QLD"] == 1.0

    # Clear red -> cash regardless of overlay
    md = {"QQQ": 95.0, "EMA_TOP": 105.0, "EMA_BOT": 100.0, **calm}
    assert s.get_allocation(None, md, {})["CASH"] == 1.0

    green = {"QQQ": 110.0, "EMA_TOP": 105.0, "EMA_BOT": 100.0}
    # Each trigger alone caps green at 1x
    assert s.get_allocation(None, {**green, **calm, "ROLL_HIGH": 140.0}, {})["QQQ"] == 1.0   # >15% off high
    assert s.get_allocation(None, {**green, **calm, "EMA_FAST": 115.0}, {})["QQQ"] == 1.0   # below fast EMA
    assert s.get_allocation(None, {**green, **calm, "RVOL": 45.0}, {})["QQQ"] == 1.0        # vol gate

    # Missing overlay inputs (warm-up) -> overlay ignored, channel rules apply
    md = {"QQQ": 110.0, "EMA_TOP": 105.0, "EMA_BOT": 100.0, "ROLL_HIGH": None, "EMA_FAST": None, "RVOL": None}
    assert s.get_allocation(None, md, {})["TQQQ"] == 1.0
