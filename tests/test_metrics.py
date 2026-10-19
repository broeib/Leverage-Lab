"""Unit tests for performance and risk metrics calculations."""

import pytest
import pandas as pd
import numpy as np
from engine.metrics import compute_performance_metrics, compute_twr_metrics, compute_weekly_returns
from engine.constants import WEEKS_PER_YEAR, RISK_FREE_RATE_ANNUAL


def test_hand_computed_twr_metrics():
    """Verify compute_twr_metrics matches hand-computed values for CAGR, maxdd, and Sharpe."""
    # 5 dates spaced by 7 days (4 weeks elapsed = 28 days)
    dates = pd.date_range("2020-01-01", periods=5, freq="7D")
    
    # Pre-defined returns: r1=0.02, r2=0.04, r3=-0.01, r4=0.03
    # twr:
    # t0: 1.0
    # t1: 1.02
    # t2: 1.0608
    # t3: 1.050192 (drawdown from 1.0608 is 1.0%)
    # t4: 1.08169776
    returns = [0.02, 0.04, -0.01, 0.03]
    twr = [1.0]
    for r in returns:
        twr.append(twr[-1] * (1.0 + r))

    # Hand computation of returns std:
    # mean = 0.02
    # diffs^2: 0, 0.0004, 0.0009, 0.0001 -> sum = 0.0014 -> var = 0.0014 / 3 = 0.0004666667
    # std = sqrt(var) = 0.021602469
    # rf_weekly:
    # t1: 0.052 / 52 = 0.001
    # t2: 0.104 / 52 = 0.002
    # t3: 0.000 / 52 = 0.000
    # t4: 0.052 / 52 = 0.001
    # excess: 0.019, 0.038, -0.010, 0.029 -> mean = 0.019
    # Sharpe = (0.019 / 0.021602469) * sqrt(52) = 6.3421... -> 6.342
    
    # Hand computation of CAGR:
    # years = 28 / 365.25 = 0.076659822
    # twr_end / twr_start = 1.08169776
    # cagr = (1.08169776 ** (1 / 0.076659822) - 1) * 100 = 178.55%

    # Hand computation of maxdd:
    # peak at t2 = 1.0608
    # trough at t3 = 1.050192
    # dd = (1.0608 - 1.050192) / 1.0608 * 100 = 1.00%

    df = pd.DataFrame(
        {
            "twr_unit": twr,
            "total_value": [1000.0 * x for x in twr],
            "total_invested": [1000.0] * 5,
            "weekly_contribution": [1000.0, 0.0, 0.0, 0.0, 0.0],
            "rf_annual": [0.052, 0.052, 0.104, 0.000, 0.052],
        },
        index=dates,
    )

    metrics = compute_twr_metrics(df)
    assert metrics["cagr"] == 178.55
    assert metrics["maxdd"] == 1.00
    assert metrics["sharpe"] == 6.342

    perf = compute_performance_metrics(df)
    assert perf["sharpe_ratio"] == 6.342


def test_metrics_fallback_to_constant_rf():
    """Verify metrics calculate Sharpe using RISK_FREE_RATE_ANNUAL when rf_annual is absent."""
    dates = pd.date_range("2020-01-01", periods=5, freq="7D")
    twr = [1.0, 1.02, 1.0608, 1.050192, 1.08169776]

    df = pd.DataFrame(
        {
            "twr_unit": twr,
            "total_value": [1000.0 * x for x in twr],
            "total_invested": [1000.0] * 5,
            "weekly_contribution": [1000.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )

    # Constant rf_weekly = 0.04 / 52 = 0.00076923
    # excess: r - 0.00076923 -> mean excess = 0.02 - 0.00076923 = 0.01923077
    # std = 0.021602469
    # Sharpe = (0.01923077 / 0.021602469) * sqrt(52) = 6.419
    m = compute_twr_metrics(df)
    assert m["sharpe"] == 6.419

    p = compute_performance_metrics(df)
    assert p["sharpe_ratio"] == 6.419


def test_compute_twr_metrics_on_subperiod_slice():
    """Verify compute_twr_metrics works accurately on a date slice of history_df."""
    dates = pd.date_range("2020-01-01", periods=10, freq="7D")
    twr = [1.0 + 0.01 * i for i in range(10)]

    df = pd.DataFrame(
        {
            "twr_unit": twr,
            "total_value": [1000.0 * x for x in twr],
            "total_invested": [1000.0] * 10,
            "weekly_contribution": [0.0] * 10,
            "rf_annual": [0.04] * 10,
        },
        index=dates,
    )

    # Slice middle 4 weeks
    sub_df = df.iloc[2:6]
    m_sub = compute_twr_metrics(sub_df)
    assert "cagr" in m_sub
    assert "sharpe" in m_sub
    assert "maxdd" in m_sub
    assert "calmar" in m_sub
    assert m_sub["maxdd"] == 0.0  # Monotonically increasing twr


def test_rebalance_count_includes_cash_alloc():
    """Verify rebalance_count detects shifts in CASH_alloc > 0.05."""
    dates = pd.date_range("2020-01-01", periods=3, freq="7D")
    df = pd.DataFrame(
        {
            "total_value": [1000.0, 1000.0, 1000.0],
            "total_invested": [1000.0, 1000.0, 1000.0],
            "weekly_contribution": [0.0, 0.0, 0.0],
            "QQQ_alloc": [0.0, 0.0, 0.0],
            "QLD_alloc": [0.0, 0.0, 0.0],
            "TQQQ_alloc": [0.0, 0.0, 0.0],
            # Shift from 0 to 100% CASH
            "CASH_alloc": [0.0, 1.0, 1.0],
        },
        index=dates,
    )

    metrics = compute_performance_metrics(df)
    # Week 1 -> Week 2: CASH_alloc shifts by 1.0 (> 0.05) -> 1 rebalance
    # Week 2 -> Week 3: CASH_alloc shifts by 0.0 (not > 0.05)
    assert metrics["rebalance_count"] == 1
