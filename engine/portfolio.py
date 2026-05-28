"""Portfolio state tracking for multi-ETF backtesting."""

from dataclasses import dataclass
from typing import Dict, List, Any
import pandas as pd
from engine.constants import VALID_TICKERS, CASH_YIELD_ANNUAL


@dataclass
class PortfolioSnapshot:
    """A snapshot of portfolio state at a point in time."""
    date: pd.Timestamp
    shares: Dict[str, float]          # {ticker: num_shares}
    prices: Dict[str, float]          # {ticker: price}
    values: Dict[str, float]          # {ticker: value}
    total_value: float
    total_invested: float
    allocation_pct: Dict[str, float]  # {ticker: percentage}
    weekly_contribution: float
    peak_value: float
    drawdown_pct: float
    value_per_dollar: float           # total_value / total_invested
    peak_value_per_dollar: float      # peak of value_per_dollar
    drawdown_pct_per_dollar: float    # drawdown on per-dollar basis


class Portfolio:
    """Tracks portfolio state across assets (e.g. QQQ, QLD, TQQQ, CASH).

    Supports:
    - Adding cash contributions
    - Rebalancing to target allocations
    - Tracking shares, values, and history snapshots
    - Computing drawdown and per-dollar drawdown from peak
    """

    def __init__(self) -> None:
        """Initialize the Portfolio with zero assets and zero starting history."""
        self.shares: Dict[str, float] = {t: 0.0 for t in VALID_TICKERS}
        self.total_invested: float = 0.0
        self.peak_value: float = 0.0
        self.peak_value_per_dollar: float = 0.0
        self.history: List[PortfolioSnapshot] = []

    def get_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value at current market prices.

        Args:
            prices: Dictionary of current asset prices {ticker: price}.

        Returns:
            float: Total value of all assets held.
        """
        return sum(self.shares[t] * prices[t] for t in VALID_TICKERS)

    def get_values_by_ticker(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate value held in each ticker asset.

        Args:
            prices: Dictionary of current asset prices.

        Returns:
            Dict[str, float]: Current USD values held in each asset.
        """
        return {t: self.shares[t] * prices[t] for t in VALID_TICKERS}

    def get_allocation_pct(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate current asset allocation percentages.

        Args:
            prices: Dictionary of current asset prices.

        Returns:
            Dict[str, float]: Allocation percentage (0.0 to 1.0) for each asset.
        """
        total = self.get_value(prices)
        if total == 0:
            return {t: 0.0 for t in VALID_TICKERS}
        return {t: (self.shares[t] * prices[t]) / total for t in VALID_TICKERS}

    def get_drawdown_pct(self, prices: Dict[str, float]) -> float:
        """Calculate current drawdown percentage from the peak absolute portfolio value.

        Args:
            prices: Dictionary of current asset prices.

        Returns:
            float: Percentage drawdown from absolute peak.
        """
        current = self.get_value(prices)
        if self.peak_value == 0:
            return 0.0
        return max(0.0, (self.peak_value - current) / self.peak_value * 100.0)

    def get_value_per_dollar(self, prices: Dict[str, float]) -> float:
        """Calculate value per dollar invested (portfolio growth efficiency).

        This represents the overall growth of $1.00 put into the portfolio.

        Args:
            prices: Dictionary of current asset prices.

        Returns:
            float: Ratio of total portfolio value to total invested cash.
        """
        if self.total_invested <= 0:
            return 0.0
        return self.get_value(prices) / self.total_invested

    def get_drawdown_pct_per_dollar(self, prices: Dict[str, float]) -> float:
        """Calculate drawdown on a per-dollar-invested basis.

        This removes the masking effect of weekly DCA cash inflows on drawdown,
        giving a true picture of the investment performance decline from peak.

        Args:
            prices: Dictionary of current asset prices.

        Returns:
            float: Percentage drawdown on a per-dollar basis.
        """
        vpd = self.get_value_per_dollar(prices)
        if self.peak_value_per_dollar <= 0:
            return 0.0
        return max(0.0, (self.peak_value_per_dollar - vpd) / self.peak_value_per_dollar * 100.0)

    def get_state(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Get current portfolio state metrics for strategy consumption.

        Args:
            prices: Dictionary of current asset prices.

        Returns:
            Dict[str, float]: Portfolio metrics like value, peak, and drawdown.
        """
        total = self.get_value(prices)
        return {
            "total_value": total,
            "peak_value": self.peak_value,
            "drawdown_pct": self.get_drawdown_pct_per_dollar(prices),
            "total_invested": self.total_invested,
            "value_per_dollar": self.get_value_per_dollar(prices),
            "peak_value_per_dollar": self.peak_value_per_dollar,
        }

    def apply_cash_yield(self) -> None:
        """Apply interest yield to cash balance held in portfolio."""
        if self.shares["CASH"] > 0:
            weekly_yield = CASH_YIELD_ANNUAL / 52.0
            self.shares["CASH"] *= (1.0 + weekly_yield)

    def rebalance(
        self,
        target_allocation: Dict[str, float],
        prices: Dict[str, float],
        contribution: float = 0.0,
    ) -> None:
        """Rebalance portfolio to target allocation, adding a contribution.

        Args:
            target_allocation: Target percentages {ticker: pct} summing to ~1.0.
            prices: Current asset prices {ticker: price}.
            contribution: Cash contribution to add before rebalancing (e.g. $5000 weekly).
        """
        # Add contribution to total invested
        self.total_invested += contribution

        # Current portfolio value + new contribution
        current_value = self.get_value(prices) + contribution

        if current_value <= 0:
            return

        # Calculate target shares for each asset
        for ticker in VALID_TICKERS:
            target_value = current_value * target_allocation.get(ticker, 0.0)
            price = prices.get(ticker, 0.0)
            if price > 0:
                self.shares[ticker] = target_value / price
            else:
                self.shares[ticker] = 0.0

        # Update absolute and per-dollar peaks
        new_value = self.get_value(prices)
        if new_value > self.peak_value:
            self.peak_value = new_value

        vpd = self.get_value_per_dollar(prices)
        if vpd > self.peak_value_per_dollar:
            self.peak_value_per_dollar = vpd

    def record_snapshot(
        self, 
        date: pd.Timestamp, 
        prices: Dict[str, float],
        contribution: float = 0.0
    ) -> PortfolioSnapshot:
        """Record a snapshot of the current portfolio state to history.

        Args:
            date: CurrentTimestamp date.
            prices: Current asset prices.
            contribution: Cash contribution made this period.

        Returns:
            PortfolioSnapshot: The recorded state snapshot.
        """
        total = self.get_value(prices)
        values = self.get_values_by_ticker(prices)
        alloc = self.get_allocation_pct(prices)
        vpd = self.get_value_per_dollar(prices)
        drawdown_per_dollar = self.get_drawdown_pct_per_dollar(prices)

        snapshot = PortfolioSnapshot(
            date=date,
            shares=dict(self.shares),
            prices=dict(prices),
            values=values,
            total_value=total,
            total_invested=self.total_invested,
            allocation_pct=alloc,
            weekly_contribution=contribution,
            peak_value=self.peak_value,
            drawdown_pct=drawdown_per_dollar,
            value_per_dollar=vpd,
            peak_value_per_dollar=self.peak_value_per_dollar,
            drawdown_pct_per_dollar=drawdown_per_dollar,
        )
        self.history.append(snapshot)
        return snapshot

    def get_history_df(self) -> pd.DataFrame:
        """Convert portfolio snapshots to a DataFrame for analysis.

        Returns:
            pd.DataFrame: Tabular history indexed by Timestamp dates.
        """
        if not self.history:
            return pd.DataFrame()

        records = []
        for snap in self.history:
            record = {
                "date": snap.date,
                "total_value": snap.total_value,
                "total_invested": snap.total_invested,
                "peak_value": snap.peak_value,
                "drawdown_pct": snap.drawdown_pct,
                "value_per_dollar": snap.value_per_dollar,
                "peak_value_per_dollar": snap.peak_value_per_dollar,
                "drawdown_pct_per_dollar": snap.drawdown_pct_per_dollar,
                "weekly_contribution": snap.weekly_contribution,
                "QQQ_value": snap.values.get("QQQ", 0.0),
                "QLD_value": snap.values.get("QLD", 0.0),
                "TQQQ_value": snap.values.get("TQQQ", 0.0),
                "CASH_value": snap.values.get("CASH", 0.0),
                "QQQ_alloc": snap.allocation_pct.get("QQQ", 0.0),
                "QLD_alloc": snap.allocation_pct.get("QLD", 0.0),
                "TQQQ_alloc": snap.allocation_pct.get("TQQQ", 0.0),
                "CASH_alloc": snap.allocation_pct.get("CASH", 0.0),
                "QQQ_shares": snap.shares.get("QQQ", 0.0),
                "QLD_shares": snap.shares.get("QLD", 0.0),
                "TQQQ_shares": snap.shares.get("TQQQ", 0.0),
                "CASH_shares": snap.shares.get("CASH", 0.0),
            }
            records.append(record)

        df = pd.DataFrame(records)
        df.set_index("date", inplace=True)
        return df
