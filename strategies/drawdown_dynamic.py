"""Strategy 6: Drawdown-Based Dynamic Allocation — de-leverages as portfolio drawdown increases."""

from typing import Dict
from strategies.base import BaseStrategy


class DrawdownDynamicStrategy(BaseStrategy):
    """Self-protective strategy that monitors portfolio drawdown from peak.

    - Drawdown < 5% (normal): 10% QQQ, 20% QLD, 70% TQQQ
    - 5% ≤ Drawdown < 10% (caution): 30% QQQ, 40% QLD, 30% TQQQ
    - 10% ≤ Drawdown < 20% (defensive): 60% QQQ, 30% QLD, 10% TQQQ
    - Drawdown ≥ 20% (preservation): 90% QQQ, 10% QLD
    """

    @property
    def name(self) -> str:
        return "Drawdown Dynamic"

    @property
    def description(self) -> str:
        return "Self-protective: automatically de-leverages as portfolio drops from peak."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        drawdown_pct = portfolio_state.get("drawdown_pct", 0.0)

        if drawdown_pct < 5.0:
            return {"QQQ": 0.10, "QLD": 0.20, "TQQQ": 0.70}
        elif drawdown_pct < 10.0:
            return {"QQQ": 0.30, "QLD": 0.40, "TQQQ": 0.30}
        elif drawdown_pct < 20.0:
            return {"QQQ": 0.60, "QLD": 0.30, "TQQQ": 0.10}
        else:
            return {"QQQ": 0.90, "QLD": 0.10, "TQQQ": 0.0}
