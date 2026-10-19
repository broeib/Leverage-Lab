"""Strategy 3: VIX Volatility Regime — uses VIX levels to scale leverage inversely with market fear."""

from typing import Dict, Optional
import numpy as np
from strategies.base import BaseStrategy
from tools.config_loader import get_strategy_params


class VIXVolatilityStrategy(BaseStrategy):
    """Reduce leverage exposure as volatility (VIX) increases.

    - VIX < 15 (calm): 20% QQQ, 30% QLD, 50% TQQQ
    - 15 ≤ VIX < 25 (normal): 30% QQQ, 40% QLD, 30% TQQQ
    - 25 ≤ VIX < 35 (elevated): 60% QQQ, 30% QLD, 10% TQQQ
    - VIX ≥ 35 (crisis): 100% QQQ
    """

    def __init__(
        self,
        low_fear: Optional[float] = None,
        normal_fear: Optional[float] = None,
        high_fear: Optional[float] = None,
    ) -> None:
        cfg = get_strategy_params("vix_volatility")
        self.low_fear = float(low_fear) if low_fear is not None else float(cfg.get("low_fear", 15.0))
        self.normal_fear = float(normal_fear) if normal_fear is not None else float(cfg.get("normal_fear", 25.0))
        self.high_fear = float(high_fear) if high_fear is not None else float(cfg.get("high_fear", 35.0))

    @property
    def name(self) -> str:
        return "VIX Volatility Regime"

    @property
    def description(self) -> str:
        return "Inversely scale leverage with VIX. Full de-leverage during market crises."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        vix = market_data.get("VIX")

        if vix is None or np.isnan(vix):
            return {"QQQ": 0.34, "QLD": 0.33, "TQQQ": 0.33}

        if vix < self.low_fear:
            return {"QQQ": 0.20, "QLD": 0.30, "TQQQ": 0.50}
        elif vix < self.normal_fear:
            return {"QQQ": 0.30, "QLD": 0.40, "TQQQ": 0.30}
        elif vix < self.high_fear:
            return {"QQQ": 0.60, "QLD": 0.30, "TQQQ": 0.10}
        else:
            return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0}
