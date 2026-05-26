"""Simple Moving Average (SMA) indicator."""

import pandas as pd


def compute_sma(prices: pd.Series, window: int) -> pd.Series:
    """Compute Simple Moving Average.

    Args:
        prices: Series of closing prices.
        window: Number of periods for the moving average.

    Returns:
        pd.Series: SMA values.
    """
    return prices.rolling(window=window, min_periods=window).mean()


def add_sma_columns(df: pd.DataFrame, price_col: str = "QQQ") -> pd.DataFrame:
    """Add SMA 50 and SMA 200 columns to a DataFrame.

    Args:
        df: DataFrame containing price data.
        price_col: Column name for the price series to use.

    Returns:
        pd.DataFrame: Original DataFrame with SMA_50 and SMA_200 columns added.
    """
    result = df.copy()
    result["SMA_50"] = compute_sma(result[price_col], 50)
    result["SMA_200"] = compute_sma(result[price_col], 200)
    return result
