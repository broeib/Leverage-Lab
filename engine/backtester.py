"""Core backtesting engine — runs strategies against historical data."""

import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from engine.portfolio import Portfolio
from strategies.base import BaseStrategy
from engine.constants import DEFAULT_WEEKLY_CONTRIBUTION, CASH_YIELD_ANNUAL, RISK_FREE_RATE_ANNUAL
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
        rf_rate: Optional[pd.Series] = None,
        slippage: float = 0.0,
        execution_lag_days: int = 1,
    ) -> None:
        """Initialize backtester with prepared historical data.

        Args:
            close_prices: DataFrame containing [QQQ, QLD, TQQQ] daily closes.
            vix_data: DataFrame containing VIX daily closes.
            indicator_data: DataFrame with all pre-computed technical indicators.
            weekly_contribution: USD added to the portfolio each week (default: 5000).
            rf_rate: Optional Series of annualized risk-free rates aligned to index.
            slippage: Proportional transaction cost per trade on turnover.
            execution_lag_days: Days after weekly signal date to execute (0=same day, 1=next trading day).
        """
        self.close_prices: pd.DataFrame = close_prices
        self.vix_data: pd.DataFrame = vix_data
        self.indicator_data: pd.DataFrame = indicator_data
        self.weekly_contribution: float = weekly_contribution
        self.slippage: float = slippage
        self.execution_lag_days: int = execution_lag_days

        if rf_rate is not None:
            if not isinstance(rf_rate.index, pd.DatetimeIndex):
                rf_rate.index = pd.to_datetime(rf_rate.index)
            if not rf_rate.index.equals(self.close_prices.index):
                self.rf_rate: Optional[pd.Series] = rf_rate.reindex(self.close_prices.index).ffill().bfill()
            else:
                self.rf_rate = rf_rate
        else:
            self.rf_rate = None

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
                if ticker in self.close_prices.columns:
                    val = self.close_prices.loc[date, ticker]
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    data[ticker] = float(val) if not pd.isna(val) else None

        # Technical indicators
        if date in self.indicator_data.index:
            row = self.indicator_data.loc[date]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            for col in self.indicator_data.columns:
                if col not in ["QQQ", "QLD", "TQQQ"]:
                    val = row[col]
                    data[col] = float(val) if not pd.isna(val) else None

        # Volatility Index (VIX)
        if date in self.vix_data.index:
            vix_val = self.vix_data.loc[date, "VIX_Close"]
            if isinstance(vix_val, pd.Series):
                vix_val = vix_val.iloc[0]
            data["VIX"] = float(vix_val) if not pd.isna(vix_val) else None
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
        strategy.reset()
        portfolio = Portfolio()
        logger.info(f"Running strategy backtest: {strategy.name}")

        prev_exec_date = None

        for signal_date in self.weekly_dates:
            # 1. Determine execution date based on execution_lag_days
            if self.execution_lag_days == 0:
                exec_date = signal_date
            else:
                try:
                    loc = self.close_prices.index.get_loc(signal_date)
                    idx = loc if isinstance(loc, int) else (loc.start if isinstance(loc, slice) else loc[0])
                except KeyError:
                    continue
                exec_idx = idx + self.execution_lag_days
                if exec_idx >= len(self.close_prices.index):
                    # If no next day exists (last week), skip that final execution
                    continue
                exec_date = self.close_prices.index[exec_idx]

            # 2. Extract signal-date market data and validate prices
            signal_market_data = self._get_market_data(signal_date)
            if not all(t in signal_market_data and signal_market_data[t] is not None for t in ["QQQ", "QLD", "TQQQ"]):
                continue

            signal_prices = {t: signal_market_data[t] for t in ["QQQ", "QLD", "TQQQ"]}
            if any(p <= 0 for p in signal_prices.values()):
                continue
            signal_prices["CASH"] = 1.0

            # 3. Extract execution-date market data and prices
            exec_market_data = self._get_market_data(exec_date)
            if not all(t in exec_market_data and exec_market_data[t] is not None for t in ["QQQ", "QLD", "TQQQ"]):
                continue

            exec_prices = {t: exec_market_data[t] for t in ["QQQ", "QLD", "TQQQ"]}
            if any(p <= 0 for p in exec_prices.values()):
                continue
            exec_prices["CASH"] = 1.0

            # 4. Determine risk-free rate for execution date
            if self.rf_rate is not None and exec_date in self.rf_rate.index:
                val = self.rf_rate.loc[exec_date]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                exec_rf = float(val) if not pd.isna(val) else CASH_YIELD_ANNUAL
                cash_yield_rf = exec_rf
                snapshot_rf = exec_rf
            else:
                cash_yield_rf = CASH_YIELD_ANNUAL
                snapshot_rf = RISK_FREE_RATE_ANNUAL

            # 5. Earn yield on cash balances from previous rebalance
            if prev_exec_date is not None:
                days_elapsed = (exec_date - prev_exec_date).days
                if days_elapsed > 0:
                    portfolio.apply_cash_yield(rf=cash_yield_rf, days=days_elapsed)

            # 6. Portfolio state passed to strategies is valued at signal-date prices
            portfolio_state = portfolio.get_state(signal_prices)

            # 7. Get allocations from strategy and validate
            raw_allocation = strategy.get_allocation(signal_date, signal_market_data, portfolio_state)
            allocation = strategy.validate_allocation(raw_allocation)

            # 8. Rebalance portfolio incorporating weekly cash contribution and slippage
            portfolio.rebalance(
                allocation,
                exec_prices,
                contribution=self.weekly_contribution,
                slippage=self.slippage,
            )

            # 9. Record state snapshot at execution date with execution prices
            portfolio.record_snapshot(
                exec_date,
                exec_prices,
                contribution=self.weekly_contribution,
                rf_annual=snapshot_rf,
            )

            prev_exec_date = exec_date

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
