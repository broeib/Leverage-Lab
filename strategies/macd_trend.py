"""Strategy 5: MACD Trend Strength — uses MACD direction and sign to measure trend strength."""

from typing import Dict
from strategies.base import BaseStrategy


class MACDTrendStrategy(BaseStrategy):
    """Allocate based on MACD line vs Signal line and MACD sign.

    - MACD > Signal & MACD > 0 (strong bullish): 10% QQQ, 20% QLD, 70% TQQQ
    - MACD > Signal & MACD ≤ 0 (emerging bullish): 20% QQQ, 50% QLD, 30% TQQQ
    - MACD ≤ Signal & MACD > 0 (fading bullish): 40% QQQ, 40% QLD, 20% TQQQ
    - MACD ≤ Signal & MACD ≤ 0 (bearish): 80% QQQ, 20% QLD
    """

    @property
    def name(self) -> str:
        return "MACD Trend Strength"

    @property
    def description(self) -> str:
        return "Four-quadrant MACD: leverage scales with trend direction and strength."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        macd = market_data.get("MACD")
        macd_signal = market_data.get("MACD_Signal")

        import numpy as np
        if macd is None or macd_signal is None or np.isnan(macd) or np.isnan(macd_signal):
            return {"QQQ": 0.34, "QLD": 0.33, "TQQQ": 0.33}

        macd_above_signal = macd > macd_signal
        macd_positive = macd > 0

        if macd_above_signal and macd_positive:
            return {"QQQ": 0.10, "QLD": 0.20, "TQQQ": 0.70}
        elif macd_above_signal and not macd_positive:
            return {"QQQ": 0.20, "QLD": 0.50, "TQQQ": 0.30}
        elif not macd_above_signal and macd_positive:
            return {"QQQ": 0.40, "QLD": 0.40, "TQQQ": 0.20}
        else:
            return {"QQQ": 0.80, "QLD": 0.20, "TQQQ": 0.0}
