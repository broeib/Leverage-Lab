"""
Download and cache historical price data for multiple ETF universes.
Supports: QQQ/QLD/TQQQ (NASDAQ-100), SOXX/USD/SOXL (Semiconductors), and SPY/SSO/UPRO (S&P 500).
Uses Yahoo Finance v8 chart API which is more reliable than the v7 download endpoint.

Backfill Synthetic Return Formula:
    synth_return = L * (index_return + dividend_yield/252)
                   - (L - 1) * (rf_annual_t + financing_spread)/252
                   - expense_ratio/252
where:
    - L: leverage multiplier (1.0, 2.0, 3.0). For L=1, (L - 1)=0 so no financing term.
    - index_return: daily return of the underlying price index (^NDX, ^SOX, ^GSPC).
    - dividend_yield: approximate annual index dividend yield.
    - rf_annual_t: 13-week T-bill rate (^IRX, quoted in percent, converted to annualized decimal).
    - financing_spread: calibrated spread over T-bills paid by the fund for leverage borrowing.
    - expense_ratio: fund annual expense ratio.

Calibration Results (overlap period vs actual fund CAGR):
    - QQQ (TQQQ 3x): spread = 0.0050 (0.50%), Model CAGR 41.57% vs Actual 41.65% (gap: -0.08 pp/yr)
    - SOXX (SOXL 3x): spread = 0.0015 (0.15%), Model CAGR 35.54% vs Actual 35.56% (gap: -0.02 pp/yr)
    - SPY (UPRO 3x): spread = 0.0240 (2.40%), Model CAGR 32.52% vs Actual 32.46% (gap: +0.06 pp/yr)
    - Default financing spread: 0.0050.
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import requests

logger = logging.getLogger(__name__)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
VIX_CACHE_FILE = os.path.join(DATA_DIR, "vix_data.csv")
RATES_CACHE_FILE = os.path.join(DATA_DIR, "rates_irx.csv")

MAX_RETRIES = 5
RETRY_DELAY = 3  # seconds

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}

# Spread over the 13-week T-bill paid on the borrowed (L - 1) exposure. Calibrated by
# running each leveraged fund against its own 1x ETF's total return (adjusted close)
# over the fund's live history, which isolates financing from the dividend assumption:
# TQQQ 0.58%, QLD 0.63%, UPRO 0.61%, SSO 0.67%, SOXL 0.89% (USD is an outlier at
# -2.7% because it tracks a different semiconductor index).
DEFAULT_FINANCING_SPREAD = 0.0060

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
        "dividend_yield": 0.008,
        "financing_spread": 0.0060,
        "leverage_params": {
            "1x": {"leverage": 1.0, "expense_ratio": 0.0020, "drag": 0.0020},
            "2x": {"leverage": 2.0, "expense_ratio": 0.0095, "drag": 0.0095},
            "3x": {"leverage": 3.0, "expense_ratio": 0.0086, "drag": 0.0086},
        },
    },
    # Note: USD tracks the Dow Jones US Semiconductors index and SOXL switched from
    # PHLX SOX to the ICE Semiconductor index in 2021, so ^SOX backfill is an approximation.
    "soxx": {
        "name": "Semiconductors (SOXX/USD/SOXL)",
        "tickers": {"1x": "SOXX", "2x": "USD", "3x": "SOXL"},
        "index": "%5ESOX",           # ^SOX  (PHLX Semiconductor Sector Index)
        "start_date": "1994-05-04",  # earliest ^SOX data on Yahoo Finance
        "cache_file": os.path.join(DATA_DIR, "etf_prices_soxx.csv"),
        "dividend_yield": 0.007,
        "financing_spread": 0.0090,  # SOXL calibration; USD fit is unreliable (index mismatch)
        "leverage_params": {
            "1x": {"leverage": 1.0, "expense_ratio": 0.0035, "drag": 0.0035},
            "2x": {"leverage": 2.0, "expense_ratio": 0.0095, "drag": 0.0095},
            "3x": {"leverage": 3.0, "expense_ratio": 0.0076, "drag": 0.0076},
        },
    },
    "spy": {
        "name": "S&P 500 (SPY/SSO/UPRO)",
        "tickers": {"1x": "SPY", "2x": "SSO", "3x": "UPRO"},
        "index": "%5EGSPC",          # ^GSPC
        "start_date": "1985-10-01",
        "cache_file": os.path.join(DATA_DIR, "etf_prices_spy.csv"),
        "dividend_yield": 0.025,     # approx. average S&P 500 yield over the 1985-2009 backfill window
        "financing_spread": 0.0060,
        "leverage_params": {
            "1x": {"leverage": 1.0, "expense_ratio": 0.000945, "drag": 0.000945},
            "2x": {"leverage": 2.0, "expense_ratio": 0.0089, "drag": 0.0089},
            "3x": {"leverage": 3.0, "expense_ratio": 0.0091, "drag": 0.0091},
        },
    },
}

# Backwards-compatible aliases
TICKERS = ["QQQ", "QLD", "TQQQ"]
START_DATE = "1985-10-01"
CACHE_FILE = UNIVERSES["qqq"]["cache_file"]


def _date_to_epoch(date_str):
    """Convert date string (YYYY-MM-DD) to Unix epoch timestamp in UTC."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _download_via_chart_api(ticker, start_date, end_date):
    """Download historical data using Yahoo Finance v8 chart API.

    Scales Open, High, and Low per row by (adjclose / raw_close) so all four
    OHLC series are consistently dividend/split-adjusted.

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
    if resp.status_code == 429:
        resp.raise_for_status()
    if resp.status_code != 200:
        return None

    data = resp.json()

    # Parse chart response
    result = data.get("chart", {}).get("result")
    if not result or len(result) == 0:
        return None

    chart = result[0]
    timestamps = chart.get("timestamp", [])
    if not timestamps:
        return None

    indicators = chart.get("indicators", {})
    quotes = indicators.get("quote", [{}])
    quote = quotes[0] if quotes else {}
    adj_close_data = indicators.get("adjclose", [{}])
    adj_close_list = adj_close_data[0].get("adjclose", quote.get("close", [])) if adj_close_data else quote.get("close", [])

    # Normalize dates interpreting epoch timestamps as UTC
    dates = pd.to_datetime(timestamps, unit="s", utc=True).tz_localize(None).normalize()

    raw_close = pd.Series(quote.get("close", []), index=dates, dtype="float64")
    raw_open = pd.Series(quote.get("open", []), index=dates, dtype="float64")
    raw_high = pd.Series(quote.get("high", []), index=dates, dtype="float64")
    raw_low = pd.Series(quote.get("low", []), index=dates, dtype="float64")
    raw_volume = pd.Series(quote.get("volume", []), index=dates, dtype="float64")
    adj_close = pd.Series(adj_close_list, index=dates, dtype="float64")

    # Guard against None / NaN / zero raw close
    factor = pd.Series(1.0, index=dates, dtype="float64")
    valid_mask = (raw_close.notna()) & (raw_close != 0) & (adj_close.notna())
    factor.loc[valid_mask] = adj_close.loc[valid_mask] / raw_close.loc[valid_mask]

    df = pd.DataFrame({
        "Open": raw_open * factor,
        "High": raw_high * factor,
        "Low": raw_low * factor,
        "Close": adj_close,
        "Volume": raw_volume,
    }, index=dates)

    df.index.name = "Date"
    df = df.dropna(how="all")
    return df


def _download_single_ticker(ticker, start_date, end_date, retries=MAX_RETRIES):
    """Download data for a single ticker with retry logic and 429 Retry-After handling."""
    for attempt in range(1, retries + 1):
        try:
            print(f"    [{ticker}] attempt {attempt}/{retries}...", end=" ", flush=True)
            data = _download_via_chart_api(ticker, start_date, end_date)

            if data is not None and len(data) > 0:
                print(f"OK ({len(data)} rows)")
                return data
            else:
                rows = len(data) if data is not None else 0
                print(f"insufficient data ({rows} rows)")

        except requests.HTTPError as e:
            delay = RETRY_DELAY * (2 ** (attempt - 1))
            if e.response is not None and e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(float(retry_after), delay)
                    except (ValueError, TypeError):
                        pass
                print(f"rate limited (429), Retry-After {delay:.1f}s...")
            else:
                print(f"HTTP error: {e}")
            if attempt < retries:
                time.sleep(delay)
                continue
            return None
        except Exception as e:
            print(f"error: {e}")

        if attempt < retries:
            delay = RETRY_DELAY * (2 ** (attempt - 1))
            print(f"    Retrying in {delay}s...")
            time.sleep(delay)

    print(f"    WARNING: Failed to download {ticker} after {retries} attempts")
    return None


def load_risk_free_rate(index: pd.DatetimeIndex, force_refresh: bool = False) -> pd.Series:
    """Load annualized risk-free rate (13-week Treasury Bill, ^IRX).

    Aligned to the provided index, annualized decimal (e.g. 0.0427 for 4.27%),
    forward-filled then back-filled, never NaN.

    Args:
        index: DatetimeIndex to align risk-free rates to.
        force_refresh: If True, re-download ^IRX even if cached.

    Returns:
        pd.Series named 'RF_RATE' indexed by `index`.
    """
    raw_series = None
    if os.path.exists(RATES_CACHE_FILE) and not force_refresh:
        try:
            cached_df = pd.read_csv(RATES_CACHE_FILE, index_col=0, parse_dates=True)
            if "RF_RATE" in cached_df.columns and len(cached_df) > 0:
                raw_series = cached_df["RF_RATE"]
            elif "Close" in cached_df.columns and len(cached_df) > 0:
                raw_series = cached_df["Close"] / 100.0
        except Exception as e:
            print(f"Error reading {RATES_CACHE_FILE}: {e}")

    if raw_series is None:
        print("Downloading ^IRX (13-week T-bill) data...")
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        data = _download_single_ticker("%5EIRX", "1985-01-01", end_date)
        if data is None or len(data) == 0:
            raise RuntimeError("Could not download ^IRX risk-free rate data.")

        # ^IRX is quoted in percent (e.g. 4.27 for 4.27%), divide by 100 for decimal
        raw_series = (data["Close"] / 100.0).dropna()
        raw_series.name = "RF_RATE"
        raw_series.index = pd.to_datetime(raw_series.index).normalize()
        raw_series = raw_series[~raw_series.index.duplicated(keep="first")].sort_index()
        raw_series.to_frame("RF_RATE").to_csv(RATES_CACHE_FILE)
        print(f"Saved risk-free rate to {RATES_CACHE_FILE} ({len(raw_series)} rows)")

    # Align to input index
    norm_idx = pd.to_datetime(index).normalize()
    aligned = raw_series.reindex(norm_idx).ffill().bfill().fillna(0.0)
    aligned.index = index
    aligned.name = "RF_RATE"
    return aligned


def _get_meta_file(universe: str) -> str:
    return os.path.join(DATA_DIR, f"cache_meta_{universe}.json")


def get_inception_dates(universe: str) -> dict:
    """Return dictionary of inception dates for a given universe.

    Returns:
        dict: {"1x": "YYYY-MM-DD", "2x": "YYYY-MM-DD", "3x": "YYYY-MM-DD"},
              or empty dict if unknown.
    """
    meta_path = _get_meta_file(universe)
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        return meta.get("inception_dates", {})
    except Exception:
        return {}


def _backfill_ticker(
    ticker_data,
    index_data,
    leverage,
    expense_ratio,
    dividend_yield=0.0,
    financing_spread=0.0,
    rf_series=None,
):
    """Backfill a single ticker using index returns, dividends, financing, and expense ratio.

    Formula:
        synth_return = L * (index_return + dividend_yield/252)
                       - (L - 1) * (rf_annual_t + financing_spread)/252
                       - expense_ratio/252
    For L=1, (L - 1) is 0 so there is no financing term.

    Args:
        ticker_data: DataFrame with actual ETF price data.
        index_data: DataFrame with underlying index data (must have 'Close' column).
        leverage: Leverage multiplier (1.0, 2.0, 3.0).
        expense_ratio: Annual fund expense ratio (e.g. 0.0086 for 0.86%).
        dividend_yield: Approximate pre-inception index dividend yield.
        financing_spread: Spread over 13-week T-bill rate for leverage borrowing.
        rf_series: Optional pd.Series of annualized risk-free rates (decimal). If None,
                   loaded via load_risk_free_rate(index_data.index).

    Returns:
        Tuple of (combined_DataFrame, n_synthetic_rows).
    """
    df = ticker_data.copy()
    df = df[~df.index.duplicated(keep="first")]
    df.index = pd.to_datetime(df.index).normalize()

    first_actual_date = df.index.min()

    # Calculate index daily return
    idx_close = index_data["Close"].copy()
    idx_returns = idx_close.pct_change()

    # Ensure first_actual_date is in the index
    if first_actual_date not in idx_close.index:
        matching_dates = idx_close.index[idx_close.index >= first_actual_date]
        if len(matching_dates) > 0:
            first_actual_date = matching_dates[0]
        else:
            first_actual_date = idx_close.index[-1]

    # Get all index dates that are <= first_actual_date
    dates_to_fill = idx_close[idx_close.index <= first_actual_date].index.sort_values()

    # Obtain risk-free rate series
    if leverage != 1.0:
        if rf_series is None:
            rf_series = load_risk_free_rate(idx_close.index)
        rf_aligned = rf_series.reindex(dates_to_fill).ffill().bfill().fillna(0.0)
        daily_financing = (leverage - 1.0) * (rf_aligned + financing_spread) / 252.0
    else:
        daily_financing = 0.0

    daily_div = leverage * (dividend_yield / 252.0)
    daily_er = expense_ratio / 252.0

    idx_ret_subset = idx_returns.reindex(dates_to_fill)
    synth_returns = (leverage * idx_ret_subset) + daily_div - daily_financing - daily_er

    # Prepare synthetic close prices anchored at first_actual_date
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
        # Scale synthetic High/Low by index intraday range
        if "High" in index_data.columns and "Low" in index_data.columns:
            high_ratio = (1.0 + (index_data["High"] / idx_close - 1.0) * leverage).reindex(synth_dates).fillna(1.0).clip(lower=1.0)
            low_ratio = (1.0 + (index_data["Low"] / idx_close - 1.0) * leverage).reindex(synth_dates).fillna(1.0).clip(lower=0.01, upper=1.0)
        else:
            high_ratio = pd.Series(1.0, index=synth_dates)
            low_ratio = pd.Series(1.0, index=synth_dates)
        synth_df["High"] = synth_df["Close"] * high_ratio
        synth_df["Low"] = synth_df["Close"] * low_ratio
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
        universe: Universe key ("qqq", "soxx", or "spy").
        force_refresh: If True, re-download even if cache exists.

    Returns:
        pd.DataFrame with MultiIndex columns (Close/QQQ, Close/QLD, etc.)
    """
    config = UNIVERSES[universe]
    cache_file = config["cache_file"]
    tickers = config["tickers"]
    generic_roles = ["QQQ", "QLD", "TQQQ"]
    start_date = config["start_date"]
    index_ticker = config["index"]
    lev_params = config["leverage_params"]
    dividend_yield = config.get("dividend_yield", 0.0)
    financing_spread = config.get("financing_spread", DEFAULT_FINANCING_SPREAD)

    # Check cache staleness and validity
    if os.path.exists(cache_file) and not force_refresh:
        # Check staleness via metadata
        meta_file = _get_meta_file(universe)
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r") as f:
                    meta = json.load(f)
                built_at_str = meta.get("built_at")
                if built_at_str:
                    built_at = datetime.fromisoformat(built_at_str)
                    age_days = (datetime.now(timezone.utc) - built_at).total_seconds() / 86400.0
                    if age_days > 7:
                        msg = f"WARNING: Cache for {universe} is {age_days:.1f} days old (built at {built_at_str})"
                        logger.warning(msg)
                        print(msg)
            except Exception as e:
                logger.warning(f"Could not check cache staleness for {universe}: {e}")

        print(f"Loading cached ETF data from {cache_file}")
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True, header=[0, 1])
        if "Close" in df.columns.get_level_values(0):
            close_tickers = df["Close"].columns.tolist()
            if all(t in close_tickers for t in generic_roles):
                print(f"  Cached data valid: {len(df)} rows")
                return df
        print("Cached data incomplete, re-downloading...")

    print(f"Downloading ETF data for {config['name']} from {start_date}...")
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Download underlying index for backfilling
    index_name = config["index"].replace("%5E", "^")
    print(f"Downloading {index_name} index for backfilling...")
    index_data = _download_single_ticker(index_ticker, start_date, end_date)
    if index_data is None or len(index_data) == 0:
        raise RuntimeError(f"Could not download {index_name} index data for backfilling.")

    index_data = index_data[~index_data.index.duplicated(keep="first")]
    index_data.index = pd.to_datetime(index_data.index).normalize()

    # Pre-fetch risk-free rates for backfilling
    rf_series = load_risk_free_rate(index_data.index, force_refresh=force_refresh)

    # Download each real ticker
    ticker_data = {}
    inception_dates = {}
    for role_key in ["1x", "2x", "3x"]:
        real_ticker = tickers[role_key]
        data = _download_single_ticker(real_ticker, start_date, end_date)
        if data is not None:
            ticker_data[role_key] = data
            inception_dates[role_key] = pd.to_datetime(data.index.min()).strftime("%Y-%m-%d")
        else:
            raise RuntimeError(
                f"Could not download data for {real_ticker}. "
                "Check your internet connection and try again."
            )

    # Persist cache metadata
    meta_payload = {
        "universe": universe,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "inception_dates": inception_dates,
    }
    try:
        with open(_get_meta_file(universe), "w") as f:
            json.dump(meta_payload, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not write cache metadata for {universe}: {e}")

    # Backfill each ticker
    backfilled_data = {}
    for role_key, generic_name in zip(["1x", "2x", "3x"], generic_roles):
        real_ticker = tickers[role_key]
        params = lev_params[role_key]
        lev = params["leverage"]
        er = params.get("expense_ratio", params.get("drag", 0.0))

        first_date = ticker_data[role_key].index.min()
        print(f"  Backfilling {real_ticker} (→{generic_name}) prior to {pd.Timestamp(first_date).date()}...")

        combined, n_synth = _backfill_ticker(
            ticker_data[role_key],
            index_data,
            lev,
            er,
            dividend_yield=dividend_yield,
            financing_spread=financing_spread,
            rf_series=rf_series,
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

    # Validation:
    # 1. Drop duplicate dates
    combined = combined[~combined.index.duplicated(keep="first")].sort_index()

    # 2. Check for non-positive closes
    if "Close" in combined.columns.get_level_values(0):
        close_df = combined["Close"]
        if (close_df <= 0).any().any():
            raise ValueError(f"Non-positive close prices found in {universe} data")

    # 3. Warn on gaps > 5 trading days (~7 calendar days)
    date_series = pd.Series(combined.index, index=combined.index)
    date_diffs = date_series.diff()
    large_gaps = date_diffs[date_diffs > pd.Timedelta(days=7)]
    if len(large_gaps) > 0:
        gap_msg = f"WARNING: Found {len(large_gaps)} trading gaps > 5 trading days in {universe} (e.g. {large_gaps.index[0].date()}: {large_gaps.iloc[0].days} days)"
        logger.warning(gap_msg)
        print(gap_msg)

    combined.to_csv(cache_file)
    print(f"Saved ETF data to {cache_file} ({len(combined)} rows)")

    return combined


def download_vix_data(force_refresh=False, start_date="1985-10-01"):
    """Download or load cached VIX data.

    Attempts to download ^VIX and pre-fill pre-1990 dates with ^VXO (S&P 100
    volatility index) if available. If ^VXO is unavailable, dates before ^VIX
    starts remain NaN (the constant 19.0 fallback has been removed).
    """
    if os.path.exists(VIX_CACHE_FILE) and not force_refresh:
        print(f"Loading cached VIX data from {VIX_CACHE_FILE}")
        df = pd.read_csv(VIX_CACHE_FILE, index_col=0, parse_dates=True)
        if len(df) > 0:
            return df
        print("Cached VIX data empty, re-downloading...")

    print("Downloading VIX data...")
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    vix = _download_single_ticker("%5EVIX", start_date, end_date)
    if vix is None or len(vix) == 0:
        raise RuntimeError(
            "Could not download VIX data. Check your internet connection and try again."
        )

    vix_series = vix["Close"].copy()
    vix_series.name = "VIX_Close"

    # Try downloading ^VXO for pre-1990 history
    try:
        print("Attempting to download ^VXO for pre-1990 volatility data...")
        vxo = _download_single_ticker("%5EVXO", start_date, end_date, retries=1)
        if vxo is not None and len(vxo) > 0:
            vxo_series = vxo["Close"].copy()
            vix_series = vix_series.combine_first(vxo_series)
            print(f"Merged ^VXO data: total {len(vix_series)} rows")
        else:
            print("^VXO unavailable; dates before ^VIX will remain NaN.")
    except Exception as e:
        print(f"^VXO download attempt failed: {e}; dates before ^VIX will remain NaN.")

    vix_close = pd.DataFrame({"VIX_Close": vix_series})
    if vix_close.index.tz is not None:
        vix_close.index = vix_close.index.tz_localize(None)
    vix_close.index = pd.to_datetime(vix_close.index).normalize()
    vix_close = vix_close[~vix_close.index.duplicated(keep="first")].sort_index()

    vix_close.to_csv(VIX_CACHE_FILE)
    print(f"Saved VIX data to {VIX_CACHE_FILE} ({len(vix_close)} rows)")
    return vix_close


def get_close_prices(etf_data):
    """Extract close prices from the multi-level DataFrame.

    Also carries the 1x ticker's daily High as ``QQQ_High`` so that
    High-based indicators (e.g. the EMA channel) can be computed downstream.
    """
    close = etf_data["Close"].copy()
    close = close.dropna()
    if "High" in etf_data.columns.get_level_values(0) and "QQQ" in etf_data["High"].columns:
        high = etf_data["High"]["QQQ"].reindex(close.index)
        # Fall back to Close where High is missing so the column never has gaps.
        close["QQQ_High"] = high.fillna(close["QQQ"])
    return close


def load_all_data(universe="qqq", force_refresh=False):
    """Load all data needed for backtesting a given universe.

    Args:
        universe: Universe key ("qqq", "soxx", or "spy").
        force_refresh: If True, re-download all data.

    Returns:
        Tuple of (close_prices, vix_data) DataFrames.
        VIX_Close may contain NaN at the very start for dates preceding ^VIX inception.
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

    # Align VIX data to close prices. Forward fill internal gaps once started,
    # but do NOT fill leading pre-1990 NaNs with 19.0.
    vix_data = vix_data.reindex(close_prices.index)
    vix_data["VIX_Close"] = vix_data["VIX_Close"].ffill()

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
    args = [a.lower() for a in sys.argv[1:]]
    force_refresh = "--refresh" in args or "-r" in args
    targets = [a for a in args if not a.startswith("-")]
    target = targets[0] if targets else "all"

    if target in ("all", "--all"):
        for u in UNIVERSES:
            print(f"\n{'=' * 60}\nFetching data for universe: {u}\n{'=' * 60}")
            close_prices, vix_data = load_all_data(universe=u, force_refresh=True)
            print(f"\nSample close prices ({u}):")
            print(close_prices.tail(3))
    elif target in UNIVERSES:
        close_prices, vix_data = load_all_data(universe=target, force_refresh=True if force_refresh else False)
        print("\nSample close prices:")
        print(close_prices.tail())
        print("\nSample VIX data:")
        print(vix_data.tail())
    else:
        print(f"Unknown universe: '{target}'. Available universes: {list(UNIVERSES.keys())} or 'all'")
