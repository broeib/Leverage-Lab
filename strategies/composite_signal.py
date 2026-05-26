"""Strategy 7: Composite Signal — combines SMA, RSI, and VIX into a single score."""

from typing import Dict
from strategies.base import BaseStrategy


class CompositeSignalStrategy(BaseStrategy):
    """Multi-indicator composite score (0-100) determines leverage level.

    - Score 75-100 (strong bull, low vol): 10% QQQ, 20% QLD, 70% TQQQ
    - Score 50-75 (moderate bull): 25% QQQ, 35% QLD, 40% TQQQ
    - Score 25-50 (uncertain): 50% QQQ, 35% QLD, 15% TQQQ
    - Score 0-25 (bearish / high vol): 80% QQQ, 20% QLD
    """

    @property
    def name(self) -> str:
        return "Composite Multi-Signal"

    @property
    def description(self) -> str:
        return "Blended SMA + RSI + VIX score for robust regime detection."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        score = market_data.get("Composite_Score")

        import numpy as np
        if score is None or np.isnan(score):
            return {"QQQ": 0.34, "QLD": 0.33, "TQQQ": 0.33}

        if score >= 75:
            return {"QQQ": 0.10, "QLD": 0.20, "TQQQ": 0.70}
        elif score >= 50:
            return {"QQQ": 0.25, "QLD": 0.35, "TQQQ": 0.40}
        elif score >= 25:
            return {"QQQ": 0.50, "QLD": 0.35, "TQQQ": 0.15}
        else:
            return {"QQQ": 0.80, "QLD": 0.20, "TQQQ": 0.0}
