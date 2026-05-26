"""Core backtesting engine — runs strategies against historical data."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

from engine.portfolio import Portfolio
from strategies.base import BaseStrategy


class BacktestResult:
    """Container for backtest results and performance metrics."""

    def __init__(self, strategy_name: str, description: str, history_df: pd.DataFrame):
        self.strategy_name = strategy_name
        self.description = description
        self.history = history_df
        self.metrics = self._compute_metrics()

    def _compute_metrics(self) -> dict:
        """Compute comprehensive performance metrics."""
        h = self.history
        if h.empty:
            return {}

        total_value = h["total_value"].iloc[-1]
        total_invested = h["total_invested"].iloc[-1]
        total_return_pct = ((total_value - total_invested) / total_invested) * 100

        # Time span
        start_date = h.index[0]
        end_date = h.index[-1]
        years = (end_date - start_date).days / 365.25

        # CAGR — use value-per-dollar growth over the full period.
        # value_per_dollar = total_value / total_invested, starting at 1.0.
        # This correctly measures per-dollar investment performance for DCA.
        if years > 0 and total_invested > 0:
            vpd_start = h["value_per_dollar"].iloc[0]
            vpd_end = h["value_per_dollar"].iloc[-1]
            if vpd_start > 0:
                cagr = ((vpd_end / vpd_start) ** (1 / years) - 1) * 100
            else:
                cagr = 0.0
            # Cap CAGR at reasonable levels for display
            cagr = min(cagr, 999.9)
        else:
            cagr = 0.0

        # Weekly returns for risk metrics — use value_per_dollar to remove
        # the distorting effect of DCA cash contributions on return calculations
        vpd_series = h["value_per_dollar"]
        meaningful = vpd_series[vpd_series > 0]
        if len(meaningful) > 1:
            weekly_returns = meaningful.pct_change().dropna()
            weekly_returns = weekly_returns.replace([np.inf, -np.inf], np.nan).dropna()
        else:
            weekly_returns = pd.Series(dtype=float)

        # Annualized volatility (weekly → annual)
        if len(weekly_returns) > 1:
            volatility = weekly_returns.std() * np.sqrt(52) * 100
        else:
            volatility = 0.0

        # Max drawdown (per-dollar basis, not masked by DCA inflows)
        max_drawdown = h["drawdown_pct_per_dollar"].max() if "drawdown_pct_per_dollar" in h.columns else 0.0

        # Sharpe ratio (annualized, assuming ~4% risk-free rate)
        risk_free_weekly = 0.04 / 52
        if len(weekly_returns) > 1 and weekly_returns.std() > 0:
            excess_returns = weekly_returns - risk_free_weekly
            sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(52)
        else:
            sharpe = 0.0

        # Sortino ratio (standard downside deviation)
        if len(weekly_returns) > 1:
            excess = weekly_returns - risk_free_weekly
            downside_diffs = np.minimum(excess, 0)
            downside_deviation = np.sqrt(np.mean(downside_diffs**2))
            if downside_deviation > 0:
                sortino = ((weekly_returns.mean() - risk_free_weekly) / downside_deviation) * np.sqrt(52)
            else:
                sortino = float("inf") if weekly_returns.mean() > risk_free_weekly else 0.0
        else:
            sortino = 0.0

        # Calmar ratio (CAGR / Max Drawdown)
        calmar = cagr / max_drawdown if max_drawdown > 0 else float("inf")

        # Count rebalancing events (when allocation changes significantly)
        rebalance_count = 0
        if "QQQ_alloc" in h.columns and len(h) > 1:
            alloc_changes = h[["QQQ_alloc", "QLD_alloc", "TQQQ_alloc"]].diff().abs()
            # Count weeks where total allocation shift > 5%
            total_shift = alloc_changes.sum(axis=1)
            rebalance_count = int((total_shift > 0.05).sum())

        # Profit
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
            "num_weeks": len(h),
            "start_date": str(start_date.date()),
            "end_date": str(end_date.date()),
            "years": round(years, 1),
        }


class Backtester:
    """Runs a strategy against historical data with weekly DCA contributions.

    The backtester:
    1. Iterates through trading weeks (using Friday closes)
    2. Computes all technical indicators
    3. Asks the strategy for target allocation
    4. Rebalances the portfolio + adds weekly contribution
    5. Records portfolio state
    """

    WEEKLY_CONTRIBUTION = 5000.0

    def __init__(
        self,
        close_prices: pd.DataFrame,
        vix_data: pd.DataFrame,
        indicator_data: pd.DataFrame,
    ):
        """Initialize backtester with prepared data.

        Args:
            close_prices: DataFrame with columns [QQQ, QLD, TQQQ], daily close prices.
            vix_data: DataFrame with column [VIX_Close], daily VIX values.
            indicator_data: DataFrame with all indicator columns pre-computed.
        """
        self.close_prices = close_prices
        self.vix_data = vix_data
        self.indicator_data = indicator_data

        # Get weekly trading dates (Fridays, or last trading day of the week)
        self.weekly_dates = self._get_weekly_dates()

    def _get_weekly_dates(self) -> List[pd.Timestamp]:
        """Get the last trading day of each week."""
        dates = self.close_prices.index
        # Group by year-week, take last date of each group
        weekly = dates.to_series().groupby(dates.to_period("W")).last()
        return weekly.tolist()

    def _get_market_data(self, date: pd.Timestamp) -> dict:
        """Get all market data and indicators for a given date.

        Args:
            date: The date to look up.

        Returns:
            Dict with prices, indicators, and VIX.
        """
        data = {}

        # Prices
        if date in self.close_prices.index:
            for ticker in ["QQQ", "QLD", "TQQQ"]:
                data[ticker] = float(self.close_prices.loc[date, ticker])

        # Technical indicators
        if date in self.indicator_data.index:
            row = self.indicator_data.loc[date]
            for col in self.indicator_data.columns:
                if col not in ["QQQ", "QLD", "TQQQ"]:
                    data[col] = float(row[col]) if not pd.isna(row[col]) else None

        # VIX
        if date in self.vix_data.index:
            data["VIX"] = float(self.vix_data.loc[date, "VIX_Close"])
        else:
            data["VIX"] = None

        return data

    def run(self, strategy: BaseStrategy) -> BacktestResult:
        """Run a single strategy through the entire backtest period.

        Args:
            strategy: Strategy instance to test.

        Returns:
            BacktestResult with full history and metrics.
        """
        portfolio = Portfolio()
        print(f"  Running: {strategy.name}...", end="", flush=True)

        for i, date in enumerate(self.weekly_dates):
            # Get market data for this date
            market_data = self._get_market_data(date)

            # Ensure we have prices for all tickers
            if not all(t in market_data for t in ["QQQ", "QLD", "TQQQ"]):
                continue

            prices = {t: market_data[t] for t in ["QQQ", "QLD", "TQQQ"]}

            # Skip if any price is 0 or negative
            if any(p <= 0 for p in prices.values()):
                continue

            # Inject CASH with a fixed price of 1.0
            prices["CASH"] = 1.0

            # Get portfolio state for strategies that need it (e.g., drawdown)
            portfolio_state = portfolio.get_state(prices)

            # Ask strategy for target allocation
            raw_allocation = strategy.get_allocation(date, market_data, portfolio_state)
            allocation = strategy.validate_allocation(raw_allocation)

            # Rebalance with weekly contribution
            portfolio.rebalance(allocation, prices, contribution=self.WEEKLY_CONTRIBUTION)

            # Record snapshot
            portfolio.record_snapshot(date, prices, contribution=self.WEEKLY_CONTRIBUTION)

        history_df = portfolio.get_history_df()
        print(f" done ({len(history_df)} weeks)")

        return BacktestResult(strategy.name, strategy.description, history_df)

    def run_all(self, strategies: List[BaseStrategy]) -> List[BacktestResult]:
        """Run multiple strategies and return all results.

        Args:
            strategies: List of strategy instances.

        Returns:
            List of BacktestResult objects.
        """
        results = []
        print(f"\nRunning {len(strategies)} strategies over {len(self.weekly_dates)} weeks...")
        print(f"Period: {self.weekly_dates[0].date()} to {self.weekly_dates[-1].date()}")
        print(f"Weekly contribution: ${self.WEEKLY_CONTRIBUTION:,.0f}\n")

        for strategy in strategies:
            result = self.run(strategy)
            results.append(result)

        return results


def generate_summary_table(results: List[BacktestResult]) -> pd.DataFrame:
    """Generate a summary comparison table of all strategies.

    Args:
        results: List of BacktestResult objects.

    Returns:
        pd.DataFrame with one row per strategy and metrics as columns.
    """
    rows = []
    for r in results:
        row = {"Strategy": r.strategy_name, **r.metrics}
        rows.append(row)

    df = pd.DataFrame(rows)

    # Sort by total return descending
    df = df.sort_values("total_return_pct", ascending=False).reset_index(drop=True)
    return df
