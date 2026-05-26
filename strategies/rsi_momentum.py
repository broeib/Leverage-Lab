"""Strategy 2: RSI Momentum — uses 14-day RSI to gauge momentum and overbought/oversold conditions."""

from typing import Dict
from strategies.base import BaseStrategy


class RSIMomentumStrategy(BaseStrategy):
    """Graduated allocation based on RSI momentum levels.

    - RSI > 70 (overbought): 70% QQQ, 30% QLD
    - 50 < RSI ≤ 70 (bullish): 30% QQQ, 30% QLD, 40% TQQQ
    - 30 ≤ RSI ≤ 50 (bearish): 60% QQQ, 40% QLD
    - RSI < 30 (oversold): 20% QQQ, 30% QLD, 50% TQQQ (contrarian)
    """

    @property
    def name(self) -> str:
        return "RSI Momentum"

    @property
    def description(self) -> str:
        return "Graduated allocation based on RSI. Contrarian: adds leverage when oversold."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        rsi = market_data.get("RSI")

        import numpy as np
        if rsi is None or np.isnan(rsi):
            return {"QQQ": 0.34, "QLD": 0.33, "TQQQ": 0.33}

        if rsi > 70:
            return {"QQQ": 0.70, "QLD": 0.30, "TQQQ": 0.0}
        elif rsi > 50:
            return {"QQQ": 0.30, "QLD": 0.30, "TQQQ": 0.40}
        elif rsi >= 30:
            return {"QQQ": 0.60, "QLD": 0.40, "TQQQ": 0.0}
        else:
            return {"QQQ": 0.20, "QLD": 0.30, "TQQQ": 0.50}
