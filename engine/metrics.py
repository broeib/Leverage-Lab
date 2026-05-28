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
    for idx in range(1, len(total_values)):
        prev_val = total_values.iloc[idx - 1]
        if prev_val > 0:
            r_t = (total_values.iloc[idx] - contributions.iloc[idx] - prev_val) / prev_val
            weekly_returns.append(r_t)
            
    if len(weekly_returns) > 1:
        s = pd.Series(weekly_returns, dtype=float)
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

    # CAGR (growth on per-dollar basis for DCA consistency)
    cagr: float = 0.0
    if years > 0 and total_invested > 0:
        vpd_start = history_df["value_per_dollar"].iloc[0]
        vpd_end = history_df["value_per_dollar"].iloc[-1]
        if vpd_start > 0:
            cagr = ((vpd_end / vpd_start) ** (1 / years) - 1) * 100
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

    # Max drawdown (on per-dollar basis to avoid DCA masking effect)
    max_drawdown: float = 0.0
    if "drawdown_pct_per_dollar" in history_df.columns:
        max_drawdown = float(history_df["drawdown_pct_per_dollar"].max())

    # Sharpe ratio (annualized, excess return over weekly risk-free rate)
    sharpe: float = 0.0
    risk_free_weekly = RISK_FREE_RATE_ANNUAL / WEEKS_PER_YEAR
    if len(weekly_returns) > 1 and weekly_returns.std() > 0:
        excess_returns = weekly_returns - risk_free_weekly
        sharpe = float((excess_returns.mean() / excess_returns.std()) * np.sqrt(WEEKS_PER_YEAR))

    # Sortino ratio (downside deviation basis)
    sortino: float = 0.0
    if len(weekly_returns) > 1:
        excess = weekly_returns - risk_free_weekly
        downside_diffs = np.minimum(excess, 0)
        downside_deviation = np.sqrt(np.mean(downside_diffs**2))
        if downside_deviation > 0:
            sortino = float(((weekly_returns.mean() - risk_free_weekly) / downside_deviation) * np.sqrt(WEEKS_PER_YEAR))
        else:
            sortino = float("inf") if weekly_returns.mean() > risk_free_weekly else 0.0

    # Calmar ratio
    calmar: float = cagr / max_drawdown if max_drawdown > 0 else float("inf")

    # Count rebalancing events (where total allocation shift > 5% week-over-week)
    rebalance_count: int = 0
    if "QQQ_alloc" in history_df.columns and len(history_df) > 1:
        alloc_cols = [c for c in ["QQQ_alloc", "QLD_alloc", "TQQQ_alloc"] if c in history_df.columns]
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
