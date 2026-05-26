"""Bollinger Bands indicator."""

import pandas as pd


def compute_bollinger_bands(
    prices: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple:
    """Compute Bollinger Bands.

    Args:
        prices: Series of closing prices.
        window: Moving average period (default 20).
        num_std: Number of standard deviations for bands (default 2.0).

    Returns:
        tuple: (middle_band, upper_band, lower_band) as pd.Series.
    """
    middle = prices.rolling(window=window, min_periods=window).mean()
    std = prices.rolling(window=window, min_periods=window).std()

    upper = middle + (num_std * std)
    lower = middle - (num_std * std)

    return middle, upper, lower


def add_bollinger_columns(
    df: pd.DataFrame, price_col: str = "QQQ", window: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """Add Bollinger Band columns to a DataFrame.

    Args:
        df: DataFrame containing price data.
        price_col: Column name for the price series.
        window: Moving average period.
        num_std: Number of standard deviations.

    Returns:
        pd.DataFrame: Original DataFrame with BB_Middle, BB_Upper, BB_Lower columns.
    """
    result = df.copy()
    middle, upper, lower = compute_bollinger_bands(result[price_col], window, num_std)
    result["BB_Middle"] = middle
    result["BB_Upper"] = upper
    result["BB_Lower"] = lower
    return result
