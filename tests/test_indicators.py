"""Unit tests for the trading system technical indicators."""

import pandas as pd
import numpy as np
import pytest

from indicators.sma import compute_sma
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from indicators.macd import compute_macd
from indicators.composite import compute_composite_score


def test_compute_sma():
    """Verify that Simple Moving Average is calculated correctly."""
    prices = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    
    # 3-period SMA
    sma = compute_sma(prices, window=3)
    
    assert len(sma) == 5
    assert pd.isna(sma.iloc[0])
    assert pd.isna(sma.iloc[1])
    assert sma.iloc[2] == 20.0  # (10 + 20 + 30) / 3
    assert sma.iloc[3] == 30.0  # (20 + 30 + 40) / 3
    assert sma.iloc[4] == 40.0  # (30 + 40 + 50) / 3


def test_compute_rsi():
    """Verify that RSI indicator returns values clamped between 0 and 100."""
    # Create an upward price series
    prices = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0])
    rsi = compute_rsi(prices, period=5)
    
    assert len(rsi) == len(prices)
    # Once warm, RSI should be high because prices only went up
    non_nan_rsi = rsi.dropna()
    assert len(non_nan_rsi) > 0
    assert all(0 <= val <= 100 for val in non_nan_rsi)


def test_compute_bollinger_bands():
    """Verify that Bollinger Bands are correctly placed around prices."""
    prices = pd.Series([10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 15.0, 13.0, 16.0])
    middle, upper, lower = compute_bollinger_bands(prices, window=5, num_std=2.0)
    
    assert len(upper) == len(prices)
    assert len(middle) == len(prices)
    assert len(lower) == len(prices)
    
    # Check middle band is equal to 5-period SMA
    sma_5 = compute_sma(prices, window=5)
    pd.testing.assert_series_equal(middle, sma_5)
    
    # Check bounds
    for idx in range(4, len(prices)):
        assert upper.iloc[idx] >= middle.iloc[idx]
        assert lower.iloc[idx] <= middle.iloc[idx]


def test_compute_macd():
    """Verify that MACD line and signal lines are generated."""
    prices = pd.Series([10.0 + i * 0.1 for i in range(40)])  # 40 periods
    macd_line, signal_line, hist = compute_macd(prices)
    
    assert len(macd_line) == len(prices)
    assert len(signal_line) == len(prices)
    assert len(hist) == len(prices)
    
    # Hist = macd_line - signal_line
    non_nan_indices = (macd_line.dropna().index).intersection(signal_line.dropna().index)
    for idx in non_nan_indices:
        assert pytest.approx(hist.loc[idx], 1e-6) == macd_line.loc[idx] - signal_line.loc[idx]


def test_compute_composite_score():
    """Test standard scoring properties of the composite indicator."""
    # 5 elements
    prices = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
    sma_50 = pd.Series([90.0, 95.0, 100.0, 105.0, 110.0])
    sma_200 = pd.Series([80.0, 82.0, 84.0, 86.0, 88.0])
    rsi = pd.Series([50.0, 60.0, 70.0, 80.0, 90.0])
    vix = pd.Series([15.0, 20.0, 25.0, 30.0, 35.0])
    
    score = compute_composite_score(prices, sma_50, sma_200, rsi, vix)
    
    assert len(score) == 5
    assert all(0 <= s <= 100 for s in score)
