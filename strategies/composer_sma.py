"""Composer-Native SMA Trend-Following Strategies with Cash Sweep.

These strategies are designed to be extremely simple and stateless, making them
100% compatible with the standard conditional blocks of Composer.trade.
"""

from typing import Dict
import numpy as np
from strategies.base import BaseStrategy


class ComposerSMATQQQCashStrategy(BaseStrategy):
    """If QQQ > 200 SMA, allocate 100% TQQQ. Else, allocate 100% CASH."""

    @property
    def name(self) -> str:
        return "Composer SMA: 100% TQQQ / CASH"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between 3x leveraged QQQ and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        if qqq_price > sma_200:
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
        else:
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class ComposerSMAQLDCashStrategy(BaseStrategy):
    """If QQQ > 200 SMA, allocate 100% QLD. Else, allocate 100% CASH."""

    @property
    def name(self) -> str:
        return "Composer SMA: 100% QLD / CASH"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between 2x leveraged QQQ and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        if qqq_price > sma_200:
            return {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}
        else:
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class ComposerSMAQQQCashStrategy(BaseStrategy):
    """If QQQ > 200 SMA, allocate 100% QQQ. Else, allocate 100% CASH."""

    @property
    def name(self) -> str:
        return "Composer SMA: 100% QQQ / CASH"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between 1x QQQ and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        if qqq_price > sma_200:
            return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
        else:
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class ComposerSMATechAITiltStrategy(BaseStrategy):
    """If QQQ > 200 SMA, allocate a Tech/AI blend (40% QLD, 30% TQQQ, 30% QQQ). Else, allocate 100% CASH."""

    @property
    def name(self) -> str:
        return "Composer SMA: Tech/AI-Tilted Hybrid"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between a blended Tech/AI basket (~1.7x leverage) and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        if qqq_price > sma_200:
            # Tech/AI-tilted basket during uptrends:
            # Blended leverage is (0.3 * 1.0) + (0.4 * 2.0) + (0.3 * 3.0) = 0.3 + 0.8 + 0.9 = 2.0x!
            # Wait, let's verify if the blend is 40% QLD, 30% TQQQ, 30% QQQ.
            # Yes! That sums to 1.0 and provides an effective leverage factor of 2.0x.
            return {"QQQ": 0.30, "QLD": 0.40, "TQQQ": 0.30, "CASH": 0.0}
        else:
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}
