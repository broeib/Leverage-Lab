"""Strategy 3: VIX Volatility Regime — uses VIX levels to scale leverage inversely with market fear."""

from typing import Dict
from strategies.base import BaseStrategy


class VIXVolatilityStrategy(BaseStrategy):
    """Reduce leverage exposure as volatility (VIX) increases.

    - VIX < 15 (calm): 20% QQQ, 30% QLD, 50% TQQQ
    - 15 ≤ VIX < 25 (normal): 30% QQQ, 40% QLD, 30% TQQQ
    - 25 ≤ VIX < 35 (elevated): 60% QQQ, 30% QLD, 10% TQQQ
    - VIX ≥ 35 (crisis): 100% QQQ
    """

    @property
    def name(self) -> str:
        return "VIX Volatility Regime"

    @property
    def description(self) -> str:
        return "Inversely scale leverage with VIX. Full de-leverage during market crises."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        vix = market_data.get("VIX")

        import numpy as np
        if vix is None or np.isnan(vix):
            return {"QQQ": 0.34, "QLD": 0.33, "TQQQ": 0.33}

        if vix < 15:
            return {"QQQ": 0.20, "QLD": 0.30, "TQQQ": 0.50}
        elif vix < 25:
            return {"QQQ": 0.30, "QLD": 0.40, "TQQQ": 0.30}
        elif vix < 35:
            return {"QQQ": 0.60, "QLD": 0.30, "TQQQ": 0.10}
        else:
            return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0}
