"""Relative Strength Index (RSI) indicator."""

import pandas as pd
import numpy as np


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI using the standard Wilder smoothing method.

    Args:
        prices: Series of closing prices.
        period: Lookback period for RSI calculation (default 14).

    Returns:
        pd.Series: RSI values (0-100).
    """
    delta = prices.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Use exponential moving average (Wilder's smoothing)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Handle division by zero (all gains, no losses)
    rsi = rsi.replace([np.inf, -np.inf], 100.0)

    return rsi


def add_rsi_column(df: pd.DataFrame, price_col: str = "QQQ", period: int = 14) -> pd.DataFrame:
    """Add RSI column to a DataFrame.

    Args:
        df: DataFrame containing price data.
        price_col: Column name for the price series.
        period: RSI lookback period.

    Returns:
        pd.DataFrame: Original DataFrame with RSI column added.
    """
    result = df.copy()
    result["RSI"] = compute_rsi(result[price_col], period)
    return result
