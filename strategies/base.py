"""Base strategy class for all trading strategies."""

from abc import ABC, abstractmethod
from typing import Dict


class BaseStrategy(ABC):
    """Abstract base class for leverage allocation strategies.

    All strategies must implement get_allocation() which returns the target
    percentage allocation across QQQ, QLD, and TQQQ.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of the strategy logic."""
        pass

    @abstractmethod
    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        """Determine target allocation for the given date.

        Args:
            date: Current date (pd.Timestamp).
            market_data: Dict with current indicator values:
                - 'QQQ', 'QLD', 'TQQQ': current prices
                - 'SMA_50', 'SMA_200': SMA values
                - 'RSI': RSI value
                - 'VIX': VIX close
                - 'BB_Upper', 'BB_Middle', 'BB_Lower': Bollinger Bands
                - 'MACD', 'MACD_Signal': MACD values
                - 'Composite_Score': Composite indicator score
            portfolio_state: Dict with portfolio info:
                - 'total_value': current portfolio value
                - 'peak_value': highest portfolio value so far
                - 'drawdown_pct': current drawdown percentage from peak

        Returns:
            Dict mapping ticker to allocation percentage (must sum to 1.0):
            e.g., {'QQQ': 0.3, 'QLD': 0.4, 'TQQQ': 0.3}
        """
        pass

    def validate_allocation(self, allocation: Dict[str, float]) -> Dict[str, float]:
        """Validate and normalize allocation to sum to 1.0.

        Args:
            allocation: Raw allocation dict.

        Returns:
            Normalized allocation dict.

        Raises:
            ValueError: If allocation contains invalid tickers or negative values.
        """
        valid_tickers = {"QQQ", "QLD", "TQQQ", "CASH"}
        for ticker in allocation:
            if ticker not in valid_tickers:
                raise ValueError(f"Invalid ticker: {ticker}")
            if allocation[ticker] < 0:
                raise ValueError(f"Negative allocation for {ticker}: {allocation[ticker]}")

        total = sum(allocation.values())
        if total == 0:
            raise ValueError("Total allocation is zero")

        # Normalize
        return {k: v / total for k, v in allocation.items()}
