"""Strategy 1: SMA Trend Regime — uses 50/200 day SMA crossovers to determine market regime."""

from typing import Dict, Optional
import numpy as np
from strategies.base import BaseStrategy
from tools.config_loader import get_strategy_params


class SMATrendStrategy(BaseStrategy):
    """Allocate based on QQQ's position relative to 50-day and 200-day SMAs.

    - Above both SMAs (strong uptrend): 100% TQQQ
    - Above 200 SMA only (mild uptrend): 100% QLD
    - Below 200 SMA (downtrend): 100% QQQ
    """

    def __init__(self, regime_allocations: Optional[Dict[str, Dict[str, float]]] = None) -> None:
        cfg = get_strategy_params("sma_trend")
        default_regimes = {
            "strong": {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0},
            "mild": {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0},
            "weak": {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0},
        }
        self.regime_allocations = regime_allocations or cfg.get("default_regime", default_regimes)

    @property
    def name(self) -> str:
        return "SMA Trend Regime"

    @property
    def description(self) -> str:
        return "Binary regime switching using 50/200 SMA. Full leverage in uptrends, none in downtrends."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        qqq_price = market_data["QQQ"]
        sma_50 = market_data.get("SMA_50")
        sma_200 = market_data.get("SMA_200")

        # Default to weak/QQQ if indicators not ready
        if sma_50 is None or sma_200 is None or np.isnan(sma_50) or np.isnan(sma_200):
            return dict(self.regime_allocations.get("weak", {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0}))

        if qqq_price > sma_50 and qqq_price > sma_200:
            # Strong uptrend: max leverage
            return dict(self.regime_allocations["strong"])
        elif qqq_price > sma_200:
            # Mild uptrend: moderate leverage
            return dict(self.regime_allocations["mild"])
        else:
            # Downtrend: no leverage
            return dict(self.regime_allocations["weak"])
