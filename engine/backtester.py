"""Core backtesting engine — runs strategies against historical data."""

import pandas as pd
from typing import Dict, List, Tuple, Any
from engine.portfolio import Portfolio
from strategies.base import BaseStrategy
from engine.constants import DEFAULT_WEEKLY_CONTRIBUTION
from engine.metrics import compute_performance_metrics
from engine.logger import logger


class BacktestResult:
    """Container for backtest results and performance metrics."""

    def __init__(self, strategy_name: str, description: str, history_df: pd.DataFrame) -> None:
        """Initialize and compute all metrics.

        Args:
            strategy_name: Name of the strategy.
            description: Description of strategy logic.
            history_df: DataFrame of portfolio historical snaps.
        """
        self.strategy_name: str = strategy_name
        self.description: str = description
        self.history: pd.DataFrame = history_df
        self.metrics: Dict[str, Any] = compute_performance_metrics(history_df)


class Backtester:
    """Runs strategies against historical price data with weekly DCA cash contributions."""

    def __init__(
        self,
        close_prices: pd.DataFrame,
        vix_data: pd.DataFrame,
        indicator_data: pd.DataFrame,
        weekly_contribution: float = DEFAULT_WEEKLY_CONTRIBUTION,
    ) -> None:
        """Initialize backtester with prepared historical data.

        Args:
            close_prices: DataFrame containing [QQQ, QLD, TQQQ] daily closes.
            vix_data: DataFrame containing VIX daily closes.
            indicator_data: DataFrame with all pre-computed technical indicators.
            weekly_contribution: USD added to the portfolio each week (default: 5000).
        """
        self.close_prices: pd.DataFrame = close_prices
        self.vix_data: pd.DataFrame = vix_data
        self.indicator_data: pd.DataFrame = indicator_data
        self.weekly_contribution: float = weekly_contribution

        # Pre-calculate weekly trade dates (typically Friday close or last trade day of week)
        self.weekly_dates: List[pd.Timestamp] = self._get_weekly_dates()

    def _get_weekly_dates(self) -> List[pd.Timestamp]:
        """Group historical indices to locate the last trading day of each calendar week."""
        dates = self.close_prices.index
        weekly = dates.to_series().groupby(dates.to_period("W")).last()
        return weekly.tolist()

    def _get_market_data(self, date: pd.Timestamp) -> Dict[str, Any]:
        """Extract prices, VIX, and all computed indicators for a given date."""
        data: Dict[str, Any] = {}

        # ETF Prices
        if date in self.close_prices.index:
            for ticker in ["QQQ", "QLD", "TQQQ"]:
                data[ticker] = float(self.close_prices.loc[date, ticker])

        # Technical indicators
        if date in self.indicator_data.index:
            row = self.indicator_data.loc[date]
            for col in self.indicator_data.columns:
                if col not in ["QQQ", "QLD", "TQQQ"]:
                    data[col] = float(row[col]) if not pd.isna(row[col]) else None

        # Volatility Index (VIX)
        if date in self.vix_data.index:
            data["VIX"] = float(self.vix_data.loc[date, "VIX_Close"])
        else:
            data["VIX"] = None

        return data

    def run(self, strategy: BaseStrategy) -> BacktestResult:
        """Run a single strategy through the backtest sequence.

        Args:
            strategy: Concrete Strategy instance to backtest.

        Returns:
            BacktestResult: Output containing metrics and history.
        """
        portfolio = Portfolio()
        logger.info(f"Running strategy backtest: {strategy.name}")

        for i, date in enumerate(self.weekly_dates):
            market_data = self._get_market_data(date)

            # Require prices for QQQ, QLD, and TQQQ to execute portfolio steps
            if not all(t in market_data for t in ["QQQ", "QLD", "TQQQ"]):
                continue

            prices = {t: market_data[t] for t in ["QQQ", "QLD", "TQQQ"]}

            # Skip periods with bad data (0 or negative prices)
            if any(p <= 0 for p in prices.values()):
                continue

            # 1. Earn yield on cash balances from previous period
            if i > 0:
                portfolio.apply_cash_yield()

            # 2. Inject CASH with index price of 1.0
            prices["CASH"] = 1.0

            # 3. Pull state snapshot to feed back into strategy decisions
            portfolio_state = portfolio.get_state(prices)

            # 4. Get allocations and validate
            raw_allocation = strategy.get_allocation(date, market_data, portfolio_state)
            allocation = strategy.validate_allocation(raw_allocation)

            # 5. Rebalance portfolio incorporating weekly cash contribution
            portfolio.rebalance(allocation, prices, contribution=self.weekly_contribution)

            # 6. Record state snapshot
            portfolio.record_snapshot(date, prices, contribution=self.weekly_contribution)

        history_df = portfolio.get_history_df()
        logger.info(f"Finished backtesting {strategy.name} ({len(history_df)} weeks)")

        return BacktestResult(strategy.name, strategy.description, history_df)

    def run_all(self, strategies: List[BaseStrategy]) -> List[BacktestResult]:
        """Orchestrate serial execution of multiple strategies.

        Args:
            strategies: List of initialized strategies.

        Returns:
            List[BacktestResult]: Execution results.
        """
        logger.info(
            f"Orchestrating backtest run for {len(strategies)} strategies over "
            f"{self.weekly_dates[0].date()} to {self.weekly_dates[-1].date()}"
        )
        return [self.run(s) for s in strategies]


def generate_summary_table(results: List[BacktestResult]) -> pd.DataFrame:
    """Compile summary performance metrics for a list of strategy results.

    Args:
        results: Backtest execution results.

    Returns:
        pd.DataFrame: Tabular metrics overview sorted by total return descending.
    """
    rows = []
    for r in results:
        row = {"Strategy": r.strategy_name, **r.metrics}
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty and "total_return_pct" in df.columns:
        df = df.sort_values("total_return_pct", ascending=False).reset_index(drop=True)
    return df
