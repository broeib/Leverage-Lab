"""MACD (Moving Average Convergence Divergence) indicator."""

import pandas as pd


def compute_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple:
    """Compute MACD line, Signal line, and Histogram.

    Args:
        prices: Series of closing prices.
        fast_period: Fast EMA period (default 12).
        slow_period: Slow EMA period (default 26).
        signal_period: Signal line EMA period (default 9).

    Returns:
        tuple: (macd_line, signal_line, histogram) as pd.Series.
    """
    ema_fast = prices.ewm(span=fast_period, min_periods=fast_period, adjust=False).mean()
    ema_slow = prices.ewm(span=slow_period, min_periods=slow_period, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def add_macd_columns(
    df: pd.DataFrame,
    price_col: str = "QQQ",
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    """Add MACD columns to a DataFrame.

    Args:
        df: DataFrame containing price data.
        price_col: Column name for the price series.

    Returns:
        pd.DataFrame: Original DataFrame with MACD, MACD_Signal, MACD_Hist columns.
    """
    result = df.copy()
    macd, signal, hist = compute_macd(
        result[price_col], fast_period, slow_period, signal_period
    )
    result["MACD"] = macd
    result["MACD_Signal"] = signal
    result["MACD_Hist"] = hist
    return result
