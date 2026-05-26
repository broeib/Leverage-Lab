"""Benchmark strategies: buy-and-hold for each ETF and equal-weight static."""

from typing import Dict
from strategies.base import BaseStrategy


class BuyHoldQQQ(BaseStrategy):
    """Baseline: 100% QQQ buy-and-hold with weekly DCA."""

    @property
    def name(self) -> str:
        return "Buy & Hold QQQ (1x)"

    @property
    def description(self) -> str:
        return "Baseline: all $5k/week into QQQ. No leverage."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0}


class BuyHoldQLD(BaseStrategy):
    """Baseline: 100% QLD buy-and-hold with weekly DCA."""

    @property
    def name(self) -> str:
        return "Buy & Hold QLD (2x)"

    @property
    def description(self) -> str:
        return "Baseline: all $5k/week into QLD. Constant 2x leverage."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        return {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0}


class BuyHoldTQQQ(BaseStrategy):
    """Baseline: 100% TQQQ buy-and-hold with weekly DCA."""

    @property
    def name(self) -> str:
        return "Buy & Hold TQQQ (3x)"

    @property
    def description(self) -> str:
        return "Baseline: all $5k/week into TQQQ. Constant 3x leverage."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0}


class EqualWeightStatic(BaseStrategy):
    """Baseline: equal-weight 33/33/33 static allocation."""

    @property
    def name(self) -> str:
        return "Equal Weight (33/33/33)"

    @property
    def description(self) -> str:
        return "Static equal allocation across all three leverage levels."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        return {"QQQ": 1 / 3, "QLD": 1 / 3, "TQQQ": 1 / 3}
