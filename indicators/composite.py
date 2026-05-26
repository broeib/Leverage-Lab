"""Composite score combining SMA trend, RSI momentum, and VIX volatility."""

import pandas as pd
import numpy as np


def compute_composite_score(
    qqq_prices: pd.Series,
    sma_50: pd.Series,
    sma_200: pd.Series,
    rsi: pd.Series,
    vix: pd.Series,
) -> pd.Series:
    """Compute a composite score (0-100) from multiple indicators.

    Scoring breakdown:
      - Trend Score (0-40):
          +25 if QQQ > 200-day SMA
          +15 if QQQ > 50-day SMA
      - Momentum Score (0-30):
          Linearly scaled from RSI: RSI=30 → 0, RSI=50 → 15, RSI=70 → 30
          Clamped to [0, 30]
      - Volatility Score (0-30):
          Inversely scaled from VIX: VIX=10 → 30, VIX=35 → 0
          Clamped to [0, 30]

    Args:
        qqq_prices: QQQ closing prices.
        sma_50: 50-day SMA of QQQ.
        sma_200: 200-day SMA of QQQ.
        rsi: 14-day RSI of QQQ.
        vix: VIX closing values.

    Returns:
        pd.Series: Composite score (0-100).
    """
    # Trend score (0-40)
    above_200 = (qqq_prices > sma_200).astype(float) * 25.0
    above_50 = (qqq_prices > sma_50).astype(float) * 15.0
    trend_score = above_200 + above_50

    # Momentum score (0-30): linear scale RSI 30→0, 70→30
    momentum_score = ((rsi - 30.0) / 40.0) * 30.0
    momentum_score = momentum_score.clip(0, 30)

    # Volatility score (0-30): inverse linear scale VIX 10→30, 35→0
    volatility_score = ((35.0 - vix) / 25.0) * 30.0
    volatility_score = volatility_score.clip(0, 30)

    composite = trend_score + momentum_score + volatility_score
    return composite.clip(0, 100)


def add_composite_column(
    df: pd.DataFrame, vix_series: pd.Series
) -> pd.DataFrame:
    """Add composite score column to a DataFrame that already has SMA and RSI columns.

    Args:
        df: DataFrame with columns QQQ, SMA_50, SMA_200, RSI.
        vix_series: VIX closing values aligned to the same dates.

    Returns:
        pd.DataFrame: Original DataFrame with Composite_Score column.
    """
    result = df.copy()
    result["Composite_Score"] = compute_composite_score(
        qqq_prices=result["QQQ"],
        sma_50=result["SMA_50"],
        sma_200=result["SMA_200"],
        rsi=result["RSI"],
        vix=vix_series,
    )
    return result
