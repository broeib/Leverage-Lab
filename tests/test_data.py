"""
Unit tests for data downloading, OHLC adjustment, backfill model, and risk-free rate loaders.
All tests are strictly offline (mocked network / synthetic DataFrames).
"""

import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pytest

from data import download_data
from data.download_data import (
    _date_to_epoch,
    _download_via_chart_api,
    _backfill_ticker,
    load_risk_free_rate,
    load_all_data,
    get_inception_dates,
)


class MockResponse:
    def __init__(self, json_data, status_code=200, headers=None):
        self._json_data = json_data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def test_utc_epoch_conversion():
    """Verify that _date_to_epoch interprets date string as UTC timestamp."""
    assert _date_to_epoch("2020-01-01") == 1577836800
    assert _date_to_epoch("1985-10-01") == 496972800


def test_ohlc_adjustment_scaling(monkeypatch):
    """Verify OHLC adjustment scales Open, High, Low by adjclose/close and guards against 0/None.
    Ensure scaled High >= scaled Close on adjusted data.
    """
    timestamps = [1577836800, 1577923200, 1578009600]  # 2020-01-01, 01-02, 01-03
    mock_payload = {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0, 200.0, 10.0],
                                "high": [105.0, 210.0, 12.0],
                                "low": [95.0, 190.0, 9.0],
                                "close": [100.0, 200.0, 0.0],  # 3rd row has 0 close
                                "volume": [1000, 2000, 500],
                            }
                        ],
                        "adjclose": [
                            {
                                "adjclose": [50.0, 100.0, 10.0],  # 2:1 split/div for rows 1-2
                            }
                        ],
                    },
                }
            ]
        }
    }

    monkeypatch.setattr(
        download_data.requests,
        "get",
        lambda url, params, headers, timeout: MockResponse(mock_payload),
    )

    df = _download_via_chart_api("TEST", "2020-01-01", "2020-01-04")
    assert df is not None
    assert len(df) == 3

    # Row 0: factor = 50 / 100 = 0.5
    assert df["Open"].iloc[0] == pytest.approx(50.0)
    assert df["High"].iloc[0] == pytest.approx(52.5)
    assert df["Low"].iloc[0] == pytest.approx(47.5)
    assert df["Close"].iloc[0] == pytest.approx(50.0)
    assert df["High"].iloc[0] >= df["Close"].iloc[0]

    # Row 1: factor = 100 / 200 = 0.5
    assert df["Open"].iloc[1] == pytest.approx(100.0)
    assert df["High"].iloc[1] == pytest.approx(105.0)
    assert df["Low"].iloc[1] == pytest.approx(95.0)
    assert df["Close"].iloc[1] == pytest.approx(100.0)
    assert df["High"].iloc[1] >= df["Close"].iloc[1]

    # Row 2: raw close was 0, factor falls back to 1.0 (no ZeroDivisionError)
    assert df["High"].iloc[2] == pytest.approx(12.0)
    assert df["Close"].iloc[2] == pytest.approx(10.0)


def test_backfill_formula_financing_and_dividends():
    """Verify synthetic return formula matches specification for L=3 and L=1."""
    dates = pd.date_range("2020-01-01", periods=5, freq="D")

    # Index: constant +1% return daily after day 0
    idx_close = [100.0, 101.0, 102.01, 103.0301, 104.060401]
    index_data = pd.DataFrame({"Close": idx_close}, index=dates)

    # Fund actual data starts on day 3 (dates[3])
    actual_dates = dates[3:]
    ticker_data = pd.DataFrame({"Close": [100.0, 102.0]}, index=actual_dates)

    rf_rate = 0.05
    rf_series = pd.Series(rf_rate, index=dates)
    er = 0.009
    div_yield = 0.02
    spread = 0.006

    # Test L=1: no financing term even if rf is high
    combined_1x, n_synth_1x = _backfill_ticker(
        ticker_data,
        index_data,
        leverage=1.0,
        expense_ratio=er,
        dividend_yield=div_yield,
        financing_spread=spread,
        rf_series=rf_series,
    )
    # Compare with a run where rf is doubled; for L=1 the output should be identical
    combined_1x_high_rf, _ = _backfill_ticker(
        ticker_data,
        index_data,
        leverage=1.0,
        expense_ratio=er,
        dividend_yield=div_yield,
        financing_spread=spread,
        rf_series=pd.Series(0.20, index=dates),
    )
    pd.testing.assert_series_equal(combined_1x["Close"], combined_1x_high_rf["Close"])

    # Daily return expected for L=1: index_return + div_yield/252 - er/252
    expected_ret_1x = 0.01 + (div_yield / 252.0) - (er / 252.0)
    calc_ret_1x = (combined_1x["Close"].iloc[2] - combined_1x["Close"].iloc[1]) / combined_1x["Close"].iloc[1]
    assert calc_ret_1x == pytest.approx(expected_ret_1x, rel=1e-5)

    # Test L=3: includes financing term (L - 1) * (rf + spread) / 252
    combined_3x, n_synth_3x = _backfill_ticker(
        ticker_data,
        index_data,
        leverage=3.0,
        expense_ratio=er,
        dividend_yield=div_yield,
        financing_spread=spread,
        rf_series=rf_series,
    )
    expected_ret_3x = (
        3.0 * (0.01 + div_yield / 252.0)
        - 2.0 * (rf_rate + spread) / 252.0
        - er / 252.0
    )
    calc_ret_3x = (combined_3x["Close"].iloc[2] - combined_3x["Close"].iloc[1]) / combined_3x["Close"].iloc[1]
    assert calc_ret_3x == pytest.approx(expected_ret_3x, rel=1e-5)


def test_splice_continuity_at_inception():
    """Verify that synthetic backfill connects continuously to actual fund data at inception."""
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    index_data = pd.DataFrame({
        "Open": 100.0,
        "High": 102.0,
        "Low": 98.0,
        "Close": np.linspace(100, 110, 10),
    }, index=dates)

    # Actual ETF starts on day 5 with price 50.0
    actual_dates = dates[5:]
    ticker_data = pd.DataFrame({
        "Open": 50.0,
        "High": 51.0,
        "Low": 49.0,
        "Close": np.linspace(50, 60, 5),
    }, index=actual_dates)

    rf_series = pd.Series(0.03, index=dates)

    combined, n_synth = _backfill_ticker(
        ticker_data,
        index_data,
        leverage=3.0,
        expense_ratio=0.01,
        dividend_yield=0.01,
        financing_spread=0.005,
        rf_series=rf_series,
    )

    inception_date = actual_dates[0]
    # Price on inception date must match actual ticker price exactly
    assert combined.loc[inception_date, "Close"] == pytest.approx(50.0)
    assert combined.loc[inception_date, "Open"] == pytest.approx(50.0)
    assert n_synth == 5


def test_load_risk_free_rate_alignment_and_no_nan(monkeypatch, tmp_path):
    """Verify load_risk_free_rate aligns to input DatetimeIndex, never contains NaN, and converts % to decimal."""
    cache_file = tmp_path / "rates_irx.csv"
    monkeypatch.setattr(download_data, "RATES_CACHE_FILE", str(cache_file))

    timestamps = [1577836800, 1578009600]  # Day 1 and Day 3 (Day 2 missing)
    mock_payload = {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [{"close": [4.25, 4.35], "open": [4.2, 4.3], "high": [4.3, 4.4], "low": [4.1, 4.2], "volume": [0, 0]}],
                        "adjclose": [{"adjclose": [4.25, 4.35]}],
                    },
                }
            ]
        }
    }
    monkeypatch.setattr(
        download_data.requests,
        "get",
        lambda url, params, headers, timeout: MockResponse(mock_payload),
    )

    query_index = pd.date_range("2019-12-31", periods=5, freq="D")
    rf = load_risk_free_rate(query_index, force_refresh=True)

    assert isinstance(rf, pd.Series)
    assert rf.name == "RF_RATE"
    assert len(rf) == len(query_index)
    assert not rf.isna().any()
    # 4.25% should be converted to 0.0425 decimal
    assert rf.loc[pd.Timestamp("2020-01-01")] == pytest.approx(0.0425)
    # Day before first data should be backfilled
    assert rf.loc[pd.Timestamp("2019-12-31")] == pytest.approx(0.0425)
    # Missing Day 2 (2020-01-02) should be forward filled
    assert rf.loc[pd.Timestamp("2020-01-02")] == pytest.approx(0.0425)


def test_vix_no_longer_filled_with_19(monkeypatch, tmp_path):
    """Verify pre-1990 VIX is NOT filled with 19.0 and contains NaN instead."""
    vix_cache = tmp_path / "vix.csv"
    monkeypatch.setattr(download_data, "VIX_CACHE_FILE", str(vix_cache))

    # Mock VIX starting in 1990
    dates_vix = pd.date_range("1990-01-02", periods=5, freq="D")
    vix_df = pd.DataFrame({"Close": [20.0, 21.0, 19.5, 22.0, 20.5]}, index=dates_vix)

    def mock_download_single_ticker(ticker, start, end, **kwargs):
        if "%5EVIX" in ticker:
            return vix_df
        return None  # VXO unavailable

    monkeypatch.setattr(download_data, "_download_single_ticker", mock_download_single_ticker)

    # ETF data spans 1985 to 1990
    dates_etf = pd.date_range("1985-10-01", periods=10, freq="D").union(dates_vix)
    cols = pd.MultiIndex.from_tuples([
        ("Close", "QQQ"), ("Close", "QLD"), ("Close", "TQQQ"),
        ("Open", "QQQ"), ("High", "QQQ"), ("Low", "QQQ"), ("Volume", "QQQ"),
    ])
    etf_mock = pd.DataFrame(100.0, index=dates_etf, columns=cols)
    monkeypatch.setattr(download_data, "download_etf_data", lambda universe, force_refresh: etf_mock)

    close_prices, vix_data = load_all_data(universe="qqq", force_refresh=True)

    assert len(close_prices) == len(vix_data)
    # Dates from 1985 should be NaN, NOT 19.0
    pre_1990_vix = vix_data.loc["1985-10-01":"1989-12-31", "VIX_Close"]
    assert len(pre_1990_vix) > 0
    assert pre_1990_vix.isna().all()
    assert (pre_1990_vix == 19.0).sum() == 0


def test_get_inception_dates_interface(tmp_path, monkeypatch):
    """Verify get_inception_dates reads from cache_meta_<universe>.json or returns {}."""
    monkeypatch.setattr(download_data, "DATA_DIR", str(tmp_path))

    # Unknown / unbuilt universe
    assert get_inception_dates("unknown_universe") == {}

    # Created metadata
    meta = {
        "universe": "qqq",
        "built_at": "2026-10-19T12:00:00+00:00",
        "inception_dates": {
            "1x": "1999-03-10",
            "2x": "2006-06-21",
            "3x": "2010-02-11",
        },
    }
    with open(tmp_path / "cache_meta_qqq.json", "w") as f:
        json.dump(meta, f)

    dates = get_inception_dates("qqq")
    assert dates == {"1x": "1999-03-10", "2x": "2006-06-21", "3x": "2010-02-11"}
