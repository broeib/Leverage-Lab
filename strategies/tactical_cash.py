"""Tactical Cash Reserve & Buy-the-Dip Strategy."""

from typing import Dict
import numpy as np
from strategies.base import BaseStrategy


class TacticalCashStrategy(BaseStrategy):
    """Dynamically hold cash and buy market downturns.

    - Overbought/Overextended (RSI > 70): Accumulate cash, reduce leverage.
      Target: 40% CASH, 40% QQQ, 20% QLD, 0% TQQQ
    - Normal Bullish (35 <= RSI <= 70 and above 200 SMA): Standard active posture.
      Target: 10% CASH, 20% QQQ, 30% QLD, 40% TQQQ
    - Correction Entry (below 200 SMA and drawdown < 15%): Accumulate more cash.
      Target: 50% CASH, 50% QQQ, 0% QLD, 0% TQQQ
    - Deep Correction / Oversold Capitulation (RSI < 35 or drawdown >= 15%):
      Deploy all cash aggressively into TQQQ and QLD.
      Target: 0% CASH, 0% QQQ, 20% QLD, 80% TQQQ
    """

    @property
    def name(self) -> str:
        return "Tactical Cash & Buy-the-Dip"

    @property
    def description(self) -> str:
        return "Saves cash during overextensions, then deploys 100% of cash into TQQQ/QLD when deep downturns occur."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        rsi = market_data.get("RSI")
        sma_200 = market_data.get("SMA_200")
        qqq_price = market_data["QQQ"]
        drawdown = portfolio_state.get("drawdown_pct", 0.0)

        # Default to safe standard QQQ/CASH if indicators not ready
        if rsi is None or sma_200 is None or np.isnan(rsi) or np.isnan(sma_200):
            return {"QQQ": 0.80, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.20}

        # Case 4: Deep Correction / Panic capitulation -> Deploy CASH
        if rsi < 35 or drawdown >= 15.0 or (qqq_price < sma_200 and drawdown >= 10.0):
            # Deploy all cash! Maximize leverage to buy the dip
            return {"QQQ": 0.0, "QLD": 0.20, "TQQQ": 0.80, "CASH": 0.0}

        # Case 1: Overbought/Overextended -> Save cash, cut leverage
        elif rsi > 70:
            return {"QQQ": 0.40, "QLD": 0.20, "TQQQ": 0.0, "CASH": 0.40}

        # Case 3: Correction entry / Bear market start -> Hold heavy cash
        elif qqq_price < sma_200:
            return {"QQQ": 0.50, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.50}

        # Case 2: Normal bullish uptrend -> Moderate leverage, minor cash buffer
        else:
            return {"QQQ": 0.20, "QLD": 0.30, "TQQQ": 0.40, "CASH": 0.10}
