"""Portfolio state tracking for multi-ETF backtesting."""

from dataclasses import dataclass, field
from typing import Dict, List
import pandas as pd
import numpy as np


@dataclass
class PortfolioSnapshot:
    """A snapshot of portfolio state at a point in time."""
    date: pd.Timestamp
    shares: Dict[str, float]        # {ticker: num_shares}
    prices: Dict[str, float]        # {ticker: price}
    values: Dict[str, float]        # {ticker: value}
    total_value: float
    total_invested: float
    allocation_pct: Dict[str, float]  # {ticker: percentage}
    weekly_contribution: float
    peak_value: float
    drawdown_pct: float


class Portfolio:
    """Tracks portfolio state across QQQ, QLD, and TQQQ.

    Supports:
    - Adding cash contributions
    - Rebalancing to target allocations
    - Tracking shares, values, and history
    - Computing drawdown from peak
    """

    TICKERS = ["QQQ", "QLD", "TQQQ", "CASH"]

    def __init__(self):
        self.shares: Dict[str, float] = {t: 0.0 for t in self.TICKERS}
        self.total_invested: float = 0.0
        self.peak_value: float = 0.0
        self.history: List[PortfolioSnapshot] = []

    def get_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value at given prices."""
        return sum(self.shares[t] * prices[t] for t in self.TICKERS)

    def get_values_by_ticker(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate value held in each ticker."""
        return {t: self.shares[t] * prices[t] for t in self.TICKERS}

    def get_allocation_pct(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate current allocation percentages."""
        total = self.get_value(prices)
        if total == 0:
            return {t: 0.0 for t in self.TICKERS}
        return {t: (self.shares[t] * prices[t]) / total for t in self.TICKERS}

    def get_drawdown_pct(self, prices: Dict[str, float]) -> float:
        """Calculate current drawdown percentage from peak."""
        current = self.get_value(prices)
        if self.peak_value == 0:
            return 0.0
        return max(0.0, (self.peak_value - current) / self.peak_value * 100.0)

    def get_state(self, prices: Dict[str, float]) -> dict:
        """Get current portfolio state for strategy consumption."""
        total = self.get_value(prices)
        return {
            "total_value": total,
            "peak_value": self.peak_value,
            "drawdown_pct": self.get_drawdown_pct(prices),
            "total_invested": self.total_invested,
        }

    def rebalance(
        self,
        target_allocation: Dict[str, float],
        prices: Dict[str, float],
        contribution: float = 0.0,
    ) -> None:
        """Rebalance portfolio to target allocation, optionally adding a contribution.

        Args:
            target_allocation: Target percentages {ticker: pct} summing to ~1.0.
            prices: Current prices {ticker: price}.
            contribution: Cash to add before rebalancing (e.g., $5000 weekly).
        """
        # Add contribution to total invested
        self.total_invested += contribution

        # Current portfolio value + new contribution
        current_value = self.get_value(prices) + contribution

        if current_value <= 0:
            return

        # Calculate target shares for each ticker
        for ticker in self.TICKERS:
            target_value = current_value * target_allocation.get(ticker, 0.0)
            if prices[ticker] > 0:
                self.shares[ticker] = target_value / prices[ticker]
            else:
                self.shares[ticker] = 0.0

        # Update peak
        new_value = self.get_value(prices)
        if new_value > self.peak_value:
            self.peak_value = new_value

    def record_snapshot(self, date: pd.Timestamp, prices: Dict[str, float],
                        contribution: float = 0.0) -> PortfolioSnapshot:
        """Record a snapshot of current state to history.

        Args:
            date: Current date.
            prices: Current prices.
            contribution: Contribution made this period.

        Returns:
            The recorded snapshot.
        """
        total = self.get_value(prices)
        values = self.get_values_by_ticker(prices)
        alloc = self.get_allocation_pct(prices)

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
            drawdown_pct=self.get_drawdown_pct(prices),
        )
        self.history.append(snapshot)
        return snapshot

    def get_history_df(self) -> pd.DataFrame:
        """Convert history to a DataFrame for analysis."""
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
                "weekly_contribution": snap.weekly_contribution,
                "QQQ_value": snap.values.get("QQQ", 0),
                "QLD_value": snap.values.get("QLD", 0),
                "TQQQ_value": snap.values.get("TQQQ", 0),
                "CASH_value": snap.values.get("CASH", 0),
                "QQQ_alloc": snap.allocation_pct.get("QQQ", 0),
                "QLD_alloc": snap.allocation_pct.get("QLD", 0),
                "TQQQ_alloc": snap.allocation_pct.get("TQQQ", 0),
                "CASH_alloc": snap.allocation_pct.get("CASH", 0),
                "QQQ_shares": snap.shares.get("QQQ", 0),
                "QLD_shares": snap.shares.get("QLD", 0),
                "TQQQ_shares": snap.shares.get("TQQQ", 0),
                "CASH_shares": snap.shares.get("CASH", 0),
            }
            records.append(record)

        df = pd.DataFrame(records)
        df.set_index("date", inplace=True)
        return df
