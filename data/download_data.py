"""
Download and cache historical price data for multiple ETF universes.
Supports: QQQ/QLD/TQQQ (NASDAQ-100) and SOXX/USD/SOXL (Semiconductors).
Uses Yahoo Finance v8 chart API which is more reliable than the v7 download endpoint.
"""

import os
import time
import json
import pandas as pd
import numpy as np
import requests
from datetime import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
VIX_CACHE_FILE = os.path.join(DATA_DIR, "vix_data.csv")

MAX_RETRIES = 5
RETRY_DELAY = 3  # seconds

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}

# ---------------------------------------------------------------------------
# Universe configurations
# ---------------------------------------------------------------------------
UNIVERSES = {
    "qqq": {
        "name": "NASDAQ-100 (QQQ/QLD/TQQQ)",
        "tickers": {"1x": "QQQ", "2x": "QLD", "3x": "TQQQ"},
        "index": "%5ENDX",           # ^NDX
        "start_date": "1985-10-01",
        "cache_file": os.path.join(DATA_DIR, "etf_prices_qqq.csv"),
        "leverage_params": {
            "1x": {"leverage": 1.0, "drag": 0.002},
            "2x": {"leverage": 2.0, "drag": 0.0075},
            "3x": {"leverage": 3.0, "drag": 0.015},
        },
    },
    "soxx": {
        "name": "Semiconductors (SOXX/USD/SOXL)",
        "tickers": {"1x": "SOXX", "2x": "USD", "3x": "SOXL"},
        "index": "%5ESOX",           # ^SOX  (PHLX Semiconductor Sector Index)
        "start_date": "1994-05-04",  # earliest ^SOX data on Yahoo Finance
        "cache_file": os.path.join(DATA_DIR, "etf_prices_soxx.csv"),
        "leverage_params": {
            "1x": {"leverage": 1.0, "drag": 0.004},
            "2x": {"leverage": 2.0, "drag": 0.0095},
            "3x": {"leverage": 3.0, "drag": 0.011},
        },
    },
}

# Backwards-compatible aliases
TICKERS = ["QQQ", "QLD", "TQQQ"]
START_DATE = "1985-10-01"
CACHE_FILE = UNIVERSES["qqq"]["cache_file"]

# Also keep the old cache path working for reading (migration)
_OLD_CACHE_FILE = os.path.join(DATA_DIR, "etf_prices.csv")


def _date_to_epoch(date_str):
    """Convert date string (YYYY-MM-DD) to Unix epoch timestamp."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp())


def _download_via_chart_api(ticker, start_date, end_date):
    """Download historical data using Yahoo Finance v8 chart API.

    Args:
        ticker: Ticker symbol.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        pd.DataFrame with OHLCV columns, or None on failure.
    """
    period1 = _date_to_epoch(start_date)
    period2 = _date_to_epoch(end_date)

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "includeAdjustedClose": "true",
    }

    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)

    if resp.status_code != 200:
        return None

    data = resp.json()

    # Parse the chart response
    result = data.get("chart", {}).get("result")
    if not result or len(result) == 0:
        return None

    chart = result[0]
    timestamps = chart.get("timestamp", [])
    if not timestamps:
        return None

    quote = chart["indicators"]["quote"][0]
    adj_close_data = chart["indicators"].get("adjclose", [{}])
    adj_close = adj_close_data[0].get("adjclose", quote.get("close", [])) if adj_close_data else quote.get("close", [])

    # Build DataFrame
    dates = pd.to_datetime(timestamps, unit="s").normalize()
    df = pd.DataFrame({
        "Open": quote.get("open", []),
        "High": quote.get("high", []),
        "Low": quote.get("low", []),
        "Close": adj_close,  # Use adjusted close
        "Volume": quote.get("volume", []),
    }, index=dates)

    df.index.name = "Date"

    # Drop rows with all NaN
    df = df.dropna(how="all")

    return df


def _download_single_ticker(ticker, start_date, end_date, retries=MAX_RETRIES):
    """Download data for a single ticker with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            print(f"    [{ticker}] attempt {attempt}/{retries}...", end=" ", flush=True)
            data = _download_via_chart_api(ticker, start_date, end_date)

            if data is not None and len(data) > 100:
                print(f"OK ({len(data)} rows)")
                return data
            else:
                rows = len(data) if data is not None else 0
                print(f"insufficient data ({rows} rows)")

        except Exception as e:
            print(f"error: {e}")

        if attempt < retries:
            delay = RETRY_DELAY * attempt
            print(f"    Retrying in {delay}s...")
            time.sleep(delay)

    print(f"    WARNING: Failed to download {ticker} after {retries} attempts")
    return None


def _backfill_ticker(ticker_data, index_data, leverage, drag):
    """Backfill a single ticker using index returns and backward compounding.

    Args:
        ticker_data: DataFrame with actual ETF price data.
        index_data: DataFrame with underlying index data (must have 'Close' column).
        leverage: Leverage multiplier (1.0, 2.0, 3.0).
        drag: Annual drag to subtract (e.g. 0.015 for 1.5%).

    Returns:
        DataFrame with synthetic + actual data combined.
    """
    df = ticker_data.copy()
    df = df[~df.index.duplicated(keep="first")]
    df.index = pd.to_datetime(df.index).normalize()

    first_actual_date = df.index.min()

    # Calculate index daily return
    idx_close = index_data["Close"].copy()
    idx_returns = idx_close.pct_change()

    # Synthetic return formula
    daily_drag = drag / 252.0
    synth_returns = (idx_returns * leverage) - daily_drag

    # Ensure first_actual_date is in the index
    if first_actual_date not in idx_close.index:
        matching_dates = idx_close.index[idx_close.index >= first_actual_date]
        if len(matching_dates) > 0:
            first_actual_date = matching_dates[0]
        else:
            first_actual_date = idx_close.index[-1]

    # Get all index dates that are <= first_actual_date
    dates_to_fill = idx_close[idx_close.index <= first_actual_date].index.sort_values()

    # Prepare synthetic close prices
    synth_close = pd.Series(index=dates_to_fill, dtype=float)
    synth_close.loc[first_actual_date] = df.loc[first_actual_date, "Close"]

    # Run backward compounding
    for i in range(len(dates_to_fill) - 1, 0, -1):
        curr_date = dates_to_fill[i]
        prev_date = dates_to_fill[i - 1]
        r = synth_returns.loc[curr_date]
        if pd.isna(r):
            synth_close.loc[prev_date] = synth_close.loc[curr_date]
        else:
            synth_close.loc[prev_date] = synth_close.loc[curr_date] / (1.0 + r)

    # Create synthetic DataFrame for pre-inception dates
    synth_dates = dates_to_fill[dates_to_fill < first_actual_date]

    if len(synth_dates) > 0:
        synth_df = pd.DataFrame(index=synth_dates)
        synth_df["Close"] = synth_close.loc[synth_dates]
        synth_df["Open"] = synth_close.loc[synth_dates]
        synth_df["High"] = synth_close.loc[synth_dates]
        synth_df["Low"] = synth_close.loc[synth_dates]
        synth_df["Volume"] = 0.0

        actual_df = df.loc[df.index >= first_actual_date]
        combined = pd.concat([synth_df, actual_df]).sort_index()
        return combined, len(synth_dates)
    else:
        return df, 0


def download_etf_data(universe="qqq", force_refresh=False):
    """Download or load cached ETF price data for a given universe.

    The output DataFrame always uses generic column names (QQQ, QLD, TQQQ)
    regardless of which universe is selected. This allows all strategies
    and indicators to work unchanged across universes.

    Args:
        universe: Universe key ("qqq" or "soxx").
        force_refresh: If True, re-download even if cache exists.

    Returns:
        pd.DataFrame with MultiIndex columns (Close/QQQ, Close/QLD, etc.)
    """
    config = UNIVERSES[universe]
    cache_file = config["cache_file"]
    tickers = config["tickers"]  # e.g. {"1x": "SOXX", "2x": "USD", "3x": "SOXL"}
    real_tickers = [tickers["1x"], tickers["2x"], tickers["3x"]]
    generic_roles = ["QQQ", "QLD", "TQQQ"]  # generic role names
    start_date = config["start_date"]
    index_ticker = config["index"]
    lev_params = config["leverage_params"]

    # Check cache
    if os.path.exists(cache_file) and not force_refresh:
        print(f"Loading cached ETF data from {cache_file}")
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True, header=[0, 1])
        if "Close" in df.columns.get_level_values(0):
            close_tickers = df["Close"].columns.tolist()
            if all(t in close_tickers for t in generic_roles):
                print(f"  Cached data valid: {len(df)} rows")
                return df
        print("Cached data incomplete, re-downloading...")

    print(f"Downloading ETF data for {config['name']} from {start_date}...")
    end_date = datetime.now().strftime("%Y-%m-%d")

    # Download the underlying index for backfilling
    index_name = config["index"].replace("%5E", "^")
    print(f"Downloading {index_name} index for backfilling...")
    index_data = _download_single_ticker(index_ticker, start_date, end_date)
    if index_data is None or len(index_data) == 0:
        raise RuntimeError(f"Could not download {index_name} index data for backfilling.")

    index_data = index_data[~index_data.index.duplicated(keep="first")]
    index_data.index = pd.to_datetime(index_data.index).normalize()

    # Download each real ticker
    ticker_data = {}
    for role_key in ["1x", "2x", "3x"]:
        real_ticker = tickers[role_key]
        data = _download_single_ticker(real_ticker, start_date, end_date)
        if data is not None:
            ticker_data[role_key] = data
        else:
            raise RuntimeError(
                f"Could not download data for {real_ticker}. "
                "Check your internet connection and try again."
            )

    # Backfill each ticker
    backfilled_data = {}
    for role_key, generic_name in zip(["1x", "2x", "3x"], generic_roles):
        real_ticker = tickers[role_key]
        params = lev_params[role_key]
        lev = params["leverage"]
        drag = params["drag"]

        first_date = ticker_data[role_key].index.min()
        print(f"  Backfilling {real_ticker} (→{generic_name}) prior to {pd.Timestamp(first_date).date()}...")

        combined, n_synth = _backfill_ticker(
            ticker_data[role_key], index_data, lev, drag
        )
        backfilled_data[generic_name] = combined
        print(f"    {real_ticker} total rows after backfill: {len(combined)} ({n_synth} synthetic)")

    # Combine into a single DataFrame with MultiIndex columns
    price_cols = ["Open", "High", "Low", "Close", "Volume"]
    combined_frames = []
    for generic_name, data in backfilled_data.items():
        for col in price_cols:
            if col in data.columns:
                s = data[col].copy()
                s.name = (col, generic_name)
                combined_frames.append(s)

    combined = pd.concat(combined_frames, axis=1)
    combined.columns = pd.MultiIndex.from_tuples(combined.columns)

    # Ensure timezone-naive index
    if combined.index.tz is not None:
        combined.index = combined.index.tz_localize(None)

    combined.to_csv(cache_file)
    print(f"Saved ETF data to {cache_file} ({len(combined)} rows)")
    return combined


def download_vix_data(force_refresh=False, start_date="1985-10-01"):
    """Download or load cached VIX data."""
    if os.path.exists(VIX_CACHE_FILE) and not force_refresh:
        print(f"Loading cached VIX data from {VIX_CACHE_FILE}")
        df = pd.read_csv(VIX_CACHE_FILE, index_col=0, parse_dates=True)
        if len(df) > 0:
            return df
        print("Cached VIX data empty, re-downloading...")

    print("Downloading VIX data...")
    end_date = datetime.now().strftime("%Y-%m-%d")

    vix = _download_single_ticker("%5EVIX", start_date, end_date)  # URL-encoded ^VIX

    if vix is None or len(vix) == 0:
        raise RuntimeError(
            "Could not download VIX data. Check your internet connection and try again."
        )

    vix_close = vix[["Close"]].copy()
    vix_close.columns = ["VIX_Close"]

    if vix_close.index.tz is not None:
        vix_close.index = vix_close.index.tz_localize(None)

    vix_close.to_csv(VIX_CACHE_FILE)
    print(f"Saved VIX data to {VIX_CACHE_FILE} ({len(vix_close)} rows)")
    return vix_close


def get_close_prices(etf_data):
    """Extract close prices from the multi-level DataFrame."""
    close = etf_data["Close"].copy()
    close = close.dropna()
    return close


def load_all_data(universe="qqq", force_refresh=False):
    """Load all data needed for backtesting a given universe.

    Args:
        universe: Universe key ("qqq" or "soxx").
        force_refresh: If True, re-download all data.

    Returns:
        Tuple of (close_prices, vix_data) DataFrames.
    """
    etf_data = download_etf_data(universe=universe, force_refresh=force_refresh)
    vix_data = download_vix_data(force_refresh=force_refresh)

    close_prices = get_close_prices(etf_data)

    if len(close_prices) == 0:
        raise RuntimeError(
            "No overlapping data found for all ETFs. "
            "Try running with force_refresh=True."
        )

    # Normalize indexes to date-only for matching
    close_prices.index = pd.to_datetime(close_prices.index).normalize()
    vix_data.index = pd.to_datetime(vix_data.index).normalize()

    # Align VIX data to close prices (backfilling pre-1990 with 19.0)
    vix_data = vix_data.reindex(close_prices.index)
    vix_data["VIX_Close"] = vix_data["VIX_Close"].ffill().fillna(19.0)

    common_dates = close_prices.index.intersection(vix_data.index)
    close_prices = close_prices.loc[common_dates]
    vix_data = vix_data.loc[common_dates]

    config = UNIVERSES[universe]
    tickers = config["tickers"]
    print(f"\nData loaded ({config['name']}): {len(close_prices)} trading days")
    print(f"Date range: {close_prices.index[0].date()} to {close_prices.index[-1].date()}")
    print(f"Tickers: {tickers['1x']}(1x), {tickers['2x']}(2x), {tickers['3x']}(3x) → generic [QQQ, QLD, TQQQ]")

    return close_prices, vix_data


if __name__ == "__main__":
    import sys
    universe = sys.argv[1] if len(sys.argv) > 1 else "qqq"
    close_prices, vix_data = load_all_data(universe=universe, force_refresh=True)
    print("\nSample close prices:")
    print(close_prices.tail())
    print("\nSample VIX data:")
    print(vix_data.tail())
