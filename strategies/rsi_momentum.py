"""Strategy 2: RSI Momentum — uses 14-day RSI to gauge momentum and overbought/oversold conditions."""

from typing import Dict, Optional
import numpy as np
from strategies.base import BaseStrategy
from tools.config_loader import get_strategy_params


class RSIMomentumStrategy(BaseStrategy):
    """Graduated allocation based on RSI momentum levels.

    - RSI > 70 (overbought): 70% QQQ, 30% QLD
    - 50 < RSI ≤ 70 (bullish): 30% QQQ, 30% QLD, 40% TQQQ
    - 30 ≤ RSI ≤ 50 (bearish): 60% QQQ, 40% QLD
    - RSI < 30 (oversold): 20% QQQ, 30% QLD, 50% TQQQ (contrarian)
    """

    def __init__(
        self,
        overbought_rsi: Optional[float] = None,
        oversold_rsi: Optional[float] = None,
        bullish_rsi: Optional[float] = None,
    ) -> None:
        cfg = get_strategy_params("rsi_momentum")
        self.overbought_rsi = (
            float(overbought_rsi) if overbought_rsi is not None else float(cfg.get("overbought_rsi", 70.0))
        )
        self.oversold_rsi = (
            float(oversold_rsi) if oversold_rsi is not None else float(cfg.get("oversold_rsi", 30.0))
        )
        self.bullish_rsi = (
            float(bullish_rsi) if bullish_rsi is not None else float(cfg.get("bullish_rsi", 50.0))
        )

    @property
    def name(self) -> str:
        return "RSI Momentum"

    @property
    def description(self) -> str:
        return "Graduated allocation based on RSI. Contrarian: adds leverage when oversold."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        rsi = market_data.get("RSI")

        if rsi is None or np.isnan(rsi):
            return {"QQQ": 0.34, "QLD": 0.33, "TQQQ": 0.33}

        if rsi > self.overbought_rsi:
            return {"QQQ": 0.70, "QLD": 0.30, "TQQQ": 0.0}
        elif rsi > self.bullish_rsi:
            return {"QQQ": 0.30, "QLD": 0.30, "TQQQ": 0.40}
        elif rsi >= self.oversold_rsi:
            return {"QQQ": 0.60, "QLD": 0.40, "TQQQ": 0.0}
        else:
            return {"QQQ": 0.20, "QLD": 0.30, "TQQQ": 0.50}
