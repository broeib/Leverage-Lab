"""Core metrics engine for backtest performance and risk analysis."""

import pandas as pd
import numpy as np
from typing import Dict, Any
from engine.constants import WEEKS_PER_YEAR, RISK_FREE_RATE_ANNUAL


def compute_weekly_returns(total_values: pd.Series, contributions: pd.Series) -> pd.Series:
    """Compute mathematically correct time-weighted weekly returns.

    Formula:
      r_t = (total_value_t - contribution_t - total_value_t-1) / total_value_t-1
    """
    weekly_returns = []
    idx_list = []
    for idx in range(1, len(total_values)):
        prev_val = total_values.iloc[idx - 1]
        if prev_val > 0:
            r_t = (total_values.iloc[idx] - contributions.iloc[idx] - prev_val) / prev_val
            weekly_returns.append(r_t)
            idx_list.append(total_values.index[idx])
            
    if len(weekly_returns) > 1:
        s = pd.Series(weekly_returns, index=idx_list, dtype=float)
        return s.replace([np.inf, -np.inf], np.nan).dropna()
    return pd.Series(dtype=float)


def compute_performance_metrics(history_df: pd.DataFrame) -> Dict[str, Any]:
    """Compute comprehensive performance and risk metrics on backtest history.

    Args:
        history_df: DataFrame containing the portfolio history with columns:
            - total_value
            - total_invested
            - value_per_dollar
            - weekly_contribution
            - drawdown_pct_per_dollar
            - QQQ_alloc, QLD_alloc, TQQQ_alloc (optional, for rebalances)

    Returns:
        Dict[str, Any]: Compiled metrics.
    """
    if history_df.empty:
        return {}

    total_value: float = float(history_df["total_value"].iloc[-1])
    total_invested: float = float(history_df["total_invested"].iloc[-1])
    total_return_pct: float = ((total_value - total_invested) / total_invested) * 100

    # Time span in years
    start_date = history_df.index[0]
    end_date = history_df.index[-1]
    years: float = (end_date - start_date).days / 365.25

    # CAGR (Time-Weighted Return basis)
    cagr: float = 0.0
    if years > 0 and "twr_unit" in history_df.columns:
        twr_start = history_df["twr_unit"].iloc[0]
        twr_end = history_df["twr_unit"].iloc[-1]
        if twr_start > 0:
            cagr = ((twr_end / twr_start) ** (1 / years) - 1) * 100
        cagr = min(cagr, 999.9)  # Cap CAGR for display sanity

    # Weekly returns for risk metrics
    weekly_returns = compute_weekly_returns(
        history_df["total_value"], 
        history_df["weekly_contribution"]
    )

    # Annualized Volatility
    volatility: float = 0.0
    if len(weekly_returns) > 1:
        volatility = float(weekly_returns.std() * np.sqrt(WEEKS_PER_YEAR) * 100)

    # Max drawdown (Time-Weighted Return basis)
    max_drawdown: float = 0.0
    if "drawdown_pct_twr" in history_df.columns:
        max_drawdown = float(history_df["drawdown_pct_twr"].max())
    elif "drawdown_pct_per_dollar" in history_df.columns:
        max_drawdown = float(history_df["drawdown_pct_per_dollar"].max())

    # Sharpe ratio (annualized, excess return over weekly risk-free rate)
    if "rf_annual" in history_df.columns:
        rf_weekly = (history_df["rf_annual"].iloc[1:] / WEEKS_PER_YEAR).values
    else:
        rf_weekly = RISK_FREE_RATE_ANNUAL / WEEKS_PER_YEAR

    sharpe: float = 0.0
    if len(weekly_returns) > 1 and weekly_returns.std() > 0:
        excess_returns = weekly_returns.values - rf_weekly
        sharpe = float((np.mean(excess_returns) / weekly_returns.std()) * np.sqrt(WEEKS_PER_YEAR))

    # Sortino ratio (downside deviation basis)
    sortino: float = 0.0
    if len(weekly_returns) > 1:
        excess = weekly_returns.values - rf_weekly
        downside_diffs = np.minimum(excess, 0)
        downside_deviation = np.sqrt(np.mean(downside_diffs**2))
        if downside_deviation > 0:
            sortino = float((np.mean(excess) / downside_deviation) * np.sqrt(WEEKS_PER_YEAR))
        else:
            sortino = float("inf") if np.mean(excess) > 0 else 0.0

    # Calmar ratio
    calmar: float = cagr / max_drawdown if max_drawdown > 0 else float("inf")

    # Count rebalancing events where the sum of absolute changes across all four
    # allocations (QQQ, QLD, TQQQ, CASH) exceeds 0.05 (5%) week-over-week.
    rebalance_count: int = 0
    if len(history_df) > 1:
        alloc_cols = [c for c in ["QQQ_alloc", "QLD_alloc", "TQQQ_alloc", "CASH_alloc"] if c in history_df.columns]
        if alloc_cols:
            alloc_changes = history_df[alloc_cols].diff().abs()
            total_shift = alloc_changes.sum(axis=1)
            rebalance_count = int((total_shift > 0.05).sum())

    profit = total_value - total_invested

    return {
        "total_value": round(total_value, 2),
        "total_invested": round(total_invested, 2),
        "profit": round(profit, 2),
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "volatility_pct": round(volatility, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(min(sortino, 99.99), 3),
        "calmar_ratio": round(min(calmar, 99.99), 3),
        "rebalance_count": rebalance_count,
        "num_weeks": len(history_df),
        "start_date": str(start_date.date()),
        "end_date": str(end_date.date()),
        "years": round(years, 1),
    }


def compute_twr_metrics(history_df: pd.DataFrame) -> Dict[str, float]:
    """Compute performance metrics (CAGR, Sharpe, Max Drawdown, Calmar) on a TWR basis.

    Must work on any date slice of a history df (used for sub-period analysis).

    Args:
        history_df: DataFrame of portfolio history or date slice containing at least
                    'twr_unit' (or fallback total_value/weekly_contribution). May contain 'rf_annual'.

    Returns:
        Dict[str, float] with keys:
            - cagr: Compound Annual Growth Rate in percent
            - sharpe: Annualized Sharpe ratio (using rf_annual if present)
            - maxdd: Maximum drawdown in percent (from peak TWR on the slice)
            - calmar: Calmar ratio (CAGR / MaxDD)
    """
    if history_df.empty or len(history_df) < 2:
        return {"cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0, "calmar": 0.0}

    # Time span in years
    start_date = history_df.index[0]
    end_date = history_df.index[-1]
    years: float = (end_date - start_date).days / 365.25

    # CAGR (Time-Weighted Return basis)
    cagr: float = 0.0
    if years > 0 and "twr_unit" in history_df.columns:
        twr_start = float(history_df["twr_unit"].iloc[0])
        twr_end = float(history_df["twr_unit"].iloc[-1])
        if twr_start > 0:
            cagr = ((twr_end / twr_start) ** (1.0 / years) - 1.0) * 100.0

    # Weekly returns (Time-Weighted Return basis)
    if "twr_unit" in history_df.columns:
        weekly_returns = history_df["twr_unit"].pct_change().iloc[1:]
        weekly_returns = weekly_returns.replace([np.inf, -np.inf], np.nan).dropna()
    else:
        weekly_returns = compute_weekly_returns(history_df["total_value"], history_df["weekly_contribution"])

    # Sharpe ratio
    sharpe: float = 0.0
    if "rf_annual" in history_df.columns:
        rf_weekly = (history_df["rf_annual"].iloc[1:] / WEEKS_PER_YEAR).values
    else:
        rf_weekly = RISK_FREE_RATE_ANNUAL / WEEKS_PER_YEAR

    if len(weekly_returns) > 1 and weekly_returns.std() > 0:
        excess_returns = weekly_returns.values - rf_weekly
        sharpe = float((np.mean(excess_returns) / weekly_returns.std()) * np.sqrt(WEEKS_PER_YEAR))

    # Max Drawdown (Time-Weighted Return basis on this slice)
    maxdd: float = 0.0
    if "twr_unit" in history_df.columns:
        cum_max = history_df["twr_unit"].cummax()
        dd = (cum_max - history_df["twr_unit"]) / cum_max * 100.0
        maxdd = float(dd.max())
    elif "drawdown_pct_twr" in history_df.columns:
        maxdd = float(history_df["drawdown_pct_twr"].max())

    # Calmar ratio
    calmar: float = (cagr / maxdd) if maxdd > 0 else (float("inf") if cagr > 0 else 0.0)

    return {
        "cagr": round(cagr, 2),
        "sharpe": round(sharpe, 3),
        "maxdd": round(maxdd, 2),
        "calmar": round(min(calmar, 99.99), 3),
    }


