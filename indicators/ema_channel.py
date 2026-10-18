"""EMA Channel indicator (port of the TradingView "PlayBit EMA" Pine Script).

The channel is bounded by two Exponential Moving Averages of the same length:
  - Top:    EMA of the daily High
  - Bottom: EMA of the daily Close

Price relative to the channel gives a three-state trend signal:
  - Close > Top          -> bullish ("green")
  - Close < Bottom       -> bearish ("red")
  - otherwise            -> neutral ("gray")
"""

import pandas as pd


def compute_ema(prices: pd.Series, length: int) -> pd.Series:
    """Compute an Exponential Moving Average matching Pine Script's ``ta.ema``.

    Pine uses the recursive form ``ema = alpha * price + (1 - alpha) * ema[1]``
    with ``alpha = 2 / (length + 1)``, which is pandas ``ewm(span=length, adjust=False)``.
    The first ``length - 1`` values are masked to NaN as a warm-up period.

    Args:
        prices: Series of prices.
        length: EMA period.

    Returns:
        pd.Series: EMA values (NaN during warm-up).
    """
    ema = prices.ewm(span=length, adjust=False).mean()
    if length > 1:
        ema.iloc[: length - 1] = float("nan")
    return ema


def add_ema_channel_columns(
    df: pd.DataFrame,
    high_col: str = "QQQ_High",
    close_col: str = "QQQ",
    length: int = 200,
) -> pd.DataFrame:
    """Add EMA_TOP (EMA of High) and EMA_BOT (EMA of Close) columns.

    If ``high_col`` is missing, the Close series is used for both bounds, which
    degrades the channel to a single EMA line.

    Args:
        df: DataFrame containing price data.
        high_col: Column with daily highs.
        close_col: Column with daily closes.
        length: EMA period for both bounds.

    Returns:
        pd.DataFrame: Original DataFrame with EMA_TOP and EMA_BOT columns added.
    """
    result = df.copy()
    high = result[high_col] if high_col in result.columns else result[close_col]
    result["EMA_TOP"] = compute_ema(high, length)
    result["EMA_BOT"] = compute_ema(result[close_col], length)
    return result


def add_risk_overlay_columns(
    df: pd.DataFrame,
    close_col: str = "QQQ",
    fast_ema: int = 100,
    high_window: int = 252,
    vol_window: int = 20,
) -> pd.DataFrame:
    """Add the inputs used by the EMA Channel v2 risk overlay.

    Columns added:
      - EMA_FAST:   EMA of Close over ``fast_ema`` days (trend-pause detector)
      - ROLL_HIGH:  rolling ``high_window``-day high of Close (drawdown breaker)
      - RVOL:       annualised realised volatility of daily returns over
                    ``vol_window`` days, in percent (volatility gate)

    Args:
        df: DataFrame containing price data.
        close_col: Column with daily closes.
        fast_ema: Period of the fast EMA.
        high_window: Lookback for the rolling high.
        vol_window: Lookback for realised volatility.

    Returns:
        pd.DataFrame: Original DataFrame with the three columns added.
    """
    result = df.copy()
    close = result[close_col]
    result["EMA_FAST"] = compute_ema(close, fast_ema)
    result["ROLL_HIGH"] = close.rolling(high_window, min_periods=high_window).max()
    result["RVOL"] = close.pct_change().rolling(vol_window).std() * (252 ** 0.5) * 100.0
    return result
