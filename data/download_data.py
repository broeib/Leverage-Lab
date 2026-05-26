"""
Download and cache historical price data for QQQ, QLD, TQQQ, and ^VIX.
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
CACHE_FILE = os.path.join(DATA_DIR, "etf_prices.csv")
VIX_CACHE_FILE = os.path.join(DATA_DIR, "vix_data.csv")

TICKERS = ["QQQ", "QLD", "TQQQ"]
START_DATE = "1985-10-01"  # Earliest available ^NDX data

MAX_RETRIES = 5
RETRY_DELAY = 3  # seconds

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


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


def download_etf_data(force_refresh=False):
    """Download or load cached ETF price data."""
    if os.path.exists(CACHE_FILE) and not force_refresh:
        print(f"Loading cached ETF data from {CACHE_FILE}")
        df = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True, header=[0, 1])
        if "Close" in df.columns.get_level_values(0):
            close_tickers = df["Close"].columns.tolist()
            if all(t in close_tickers for t in TICKERS):
                print(f"  Cached data valid: {len(df)} rows")
                return df
        print("Cached data incomplete, re-downloading...")

    print(f"Downloading ETF data for {TICKERS} from {START_DATE}...")
    end_date = datetime.now().strftime("%Y-%m-%d")

    # Download NDX index for backfilling
    print("Downloading NASDAQ-100 (^NDX) index for backfilling...")
    ndx_data = _download_single_ticker("%5ENDX", START_DATE, end_date)
    if ndx_data is None or len(ndx_data) == 0:
        raise RuntimeError("Could not download NASDAQ-100 index (^NDX) data for backfilling.")

    ndx_data = ndx_data[~ndx_data.index.duplicated(keep="first")]
    ndx_data.index = pd.to_datetime(ndx_data.index).normalize()

    # Download each ticker individually
    ticker_data = {}
    for ticker in TICKERS:
        data = _download_single_ticker(ticker, START_DATE, end_date)
        if data is not None:
            ticker_data[ticker] = data
        else:
            raise RuntimeError(
                f"Could not download data for {ticker}. "
                "Check your internet connection and try again."
            )

    # Leverage and drag parameters for each ticker
    leverage_params = {
        "QQQ": {"leverage": 1.0, "drag": 0.002},
        "QLD": {"leverage": 2.0, "drag": 0.0075},
        "TQQQ": {"leverage": 3.0, "drag": 0.015}
    }

    # For each ticker, perform synthetic backfill
    for ticker in TICKERS:
        df = ticker_data[ticker]
        params = leverage_params[ticker]
        lev = params["leverage"]
        drag = params["drag"]

        df = df[~df.index.duplicated(keep="first")]
        df.index = pd.to_datetime(df.index).normalize()

        first_actual_date = df.index.min()
        print(f"  Backfilling {ticker} prior to {first_actual_date.date()}...")

        # Calculate NDX daily return
        ndx_close = ndx_data["Close"].copy()
        ndx_returns = ndx_close.pct_change()

        # Synthetic return formula:
        daily_drag = drag / 252.0
        synth_returns = (ndx_returns * lev) - daily_drag

        # Ensure first_actual_date is in ndx_close.index
        if first_actual_date not in ndx_close.index:
            matching_dates = ndx_close.index[ndx_close.index >= first_actual_date]
            if len(matching_dates) > 0:
                first_actual_date = matching_dates[0]
            else:
                first_actual_date = ndx_close.index[-1]

        # Get all NDX dates that are <= first_actual_date and sort them
        dates_to_fill = ndx_close[ndx_close.index <= first_actual_date].index.sort_values()

        # Prepare Series to hold synthetic Close
        synth_close = pd.Series(index=dates_to_fill, dtype=float)
        synth_close.loc[first_actual_date] = df.loc[first_actual_date, "Close"]

        # Run the backward compounding loop
        for i in range(len(dates_to_fill) - 1, 0, -1):
            curr_date = dates_to_fill[i]
            prev_date = dates_to_fill[i-1]
            r = synth_returns.loc[curr_date]
            if pd.isna(r):
                synth_close.loc[prev_date] = synth_close.loc[curr_date]
            else:
                synth_close.loc[prev_date] = synth_close.loc[curr_date] / (1.0 + r)

        # Create a new DataFrame for synthetic historical period
        synth_dates = dates_to_fill[dates_to_fill < first_actual_date]
        
        if len(synth_dates) > 0:
            synth_df = pd.DataFrame(index=synth_dates)
            synth_df["Close"] = synth_close.loc[synth_dates]
            synth_df["Open"] = synth_close.loc[synth_dates]
            synth_df["High"] = synth_close.loc[synth_dates]
            synth_df["Low"] = synth_close.loc[synth_dates]
            synth_df["Volume"] = 0.0

            # Combine synthetic history and actual data
            actual_df = df.loc[df.index >= first_actual_date]
            combined_df = pd.concat([synth_df, actual_df]).sort_index()
            ticker_data[ticker] = combined_df
            print(f"    {ticker} total rows after backfill: {len(combined_df)}")
        else:
            print(f"    No backfill needed for {ticker}")

    # Combine into a single DataFrame with MultiIndex columns
    price_cols = ["Open", "High", "Low", "Close", "Volume"]
    combined_frames = []
    for ticker, data in ticker_data.items():
        for col in price_cols:
            if col in data.columns:
                s = data[col].copy()
                s.name = (col, ticker)
                combined_frames.append(s)

    combined = pd.concat(combined_frames, axis=1)
    combined.columns = pd.MultiIndex.from_tuples(combined.columns)

    # Ensure timezone-naive index
    if combined.index.tz is not None:
        combined.index = combined.index.tz_localize(None)

    combined.to_csv(CACHE_FILE)
    print(f"Saved ETF data to {CACHE_FILE} ({len(combined)} rows)")
    return combined


def download_vix_data(force_refresh=False):
    """Download or load cached VIX data."""
    if os.path.exists(VIX_CACHE_FILE) and not force_refresh:
        print(f"Loading cached VIX data from {VIX_CACHE_FILE}")
        df = pd.read_csv(VIX_CACHE_FILE, index_col=0, parse_dates=True)
        if len(df) > 0:
            return df
        print("Cached VIX data empty, re-downloading...")

    print("Downloading VIX data...")
    end_date = datetime.now().strftime("%Y-%m-%d")

    vix = _download_single_ticker("%5EVIX", START_DATE, end_date)  # URL-encoded ^VIX

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


def load_all_data(force_refresh=False):
    """Load all data needed for backtesting."""
    etf_data = download_etf_data(force_refresh=force_refresh)
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

    print(f"\nData loaded: {len(close_prices)} trading days")
    print(f"Date range: {close_prices.index[0].date()} to {close_prices.index[-1].date()}")
    print(f"Tickers: {list(close_prices.columns)}")

    return close_prices, vix_data


if __name__ == "__main__":
    close_prices, vix_data = load_all_data(force_refresh=True)
    print("\nSample close prices:")
    print(close_prices.tail())
    print("\nSample VIX data:")
    print(vix_data.tail())
