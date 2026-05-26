"""Strategy 4: Bollinger Band Mean Reversion — uses Bollinger Bands to identify overextension."""

from typing import Dict
from strategies.base import BaseStrategy


class BollingerReversionStrategy(BaseStrategy):
    """Contrarian allocation based on Bollinger Band position.

    - Above upper band (overextended): 70% QQQ, 30% QLD
    - Between upper band & middle (healthy): 20% QQQ, 30% QLD, 50% TQQQ
    - Between middle & lower (weakening): 50% QQQ, 50% QLD
    - Below lower band (oversold): 10% QQQ, 30% QLD, 60% TQQQ
    """

    @property
    def name(self) -> str:
        return "Bollinger Mean Reversion"

    @property
    def description(self) -> str:
        return "Contrarian: reduce leverage when overextended, add when oversold."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        qqq_price = market_data["QQQ"]
        bb_upper = market_data.get("BB_Upper")
        bb_middle = market_data.get("BB_Middle")
        bb_lower = market_data.get("BB_Lower")

        import numpy as np
        if any(v is None or (isinstance(v, float) and np.isnan(v))
               for v in [bb_upper, bb_middle, bb_lower]):
            return {"QQQ": 0.34, "QLD": 0.33, "TQQQ": 0.33}

        if qqq_price > bb_upper:
            return {"QQQ": 0.70, "QLD": 0.30, "TQQQ": 0.0}
        elif qqq_price > bb_middle:
            return {"QQQ": 0.20, "QLD": 0.30, "TQQQ": 0.50}
        elif qqq_price > bb_lower:
            return {"QQQ": 0.50, "QLD": 0.50, "TQQQ": 0.0}
        else:
            return {"QQQ": 0.10, "QLD": 0.30, "TQQQ": 0.60}
