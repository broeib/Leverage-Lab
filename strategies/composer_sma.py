"""Composer-Native SMA Trend-Following Strategies with Cash Sweep.

These strategies are designed to be extremely simple and stateless, making them
100% compatible with the standard conditional blocks of Composer.trade.
They utilize a single 200-day Simple Moving Average (SMA) filter on unleveraged QQQ
to determine market regime, switching between leveraged exposure and yield-bearing cash.
"""

from typing import Dict
import numpy as np
from strategies.base import BaseStrategy


class ComposerSMATQQQCashStrategy(BaseStrategy):
    """Composer SMA: 100% TQQQ / CASH.
    
    If the close price of QQQ is above its 200-day Simple Moving Average (SMA), 
    allocate 100% of the portfolio to the 3x leveraged QQQ ETF (TQQQ). 
    Otherwise, de-leverage completely to 100% CASH (earning interest yield).
    
    This is a stateless, Composer-native trend-following strategy designed
    to maximize bull-market gains while completely avoiding bear-market drawdowns.
    """

    @property
    def name(self) -> str:
        return "Composer SMA: 100% TQQQ / CASH"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between 3x leveraged QQQ and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        # Extract underlying price and indicators
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready to avoid trading on partial data
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        # Check trend: Bull vs Bear switch
        if qqq_price > sma_200:
            # Price above 200 SMA: allocate full power to 3x leverage (TQQQ)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
        else:
            # Price below 200 SMA: retreat to safety and earn interest yield (CASH)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class ComposerSMAQLDCashStrategy(BaseStrategy):
    """Composer SMA: 100% QLD / CASH.
    
    If the close price of QQQ is above its 200-day Simple Moving Average (SMA), 
    allocate 100% of the portfolio to the 2x leveraged QQQ ETF (QLD). 
    Otherwise, de-leverage completely to 100% CASH (earning interest yield).
    
    This is a stateless, Composer-native trend-following strategy that seeks
    high leveraged returns while moderating volatility decay compared to 3x options.
    """

    @property
    def name(self) -> str:
        return "Composer SMA: 100% QLD / CASH"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between 2x leveraged QQQ and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        # Extract underlying price and indicators
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        # Check trend: Bull vs Bear switch
        if qqq_price > sma_200:
            # Price above 200 SMA: allocate to moderate 2x leverage (QLD)
            return {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}
        else:
            # Price below 200 SMA: retreat to safety and earn interest yield (CASH)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class ComposerSMAQQQCashStrategy(BaseStrategy):
    """Composer SMA: 100% QQQ / CASH.
    
    If the close price of QQQ is above its 200-day Simple Moving Average (SMA), 
    allocate 100% of the portfolio to the 1x unleveraged QQQ ETF. 
    Otherwise, de-leverage completely to 100% CASH (earning interest yield).
    
    This is a stateless, Composer-native trend-following strategy focusing on
    capital preservation, completely eliminating leverage risk while maintaining trend participation.
    """

    @property
    def name(self) -> str:
        return "Composer SMA: 100% QQQ / CASH"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between 1x QQQ and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        # Extract underlying price and indicators
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        # Check trend: Bull vs Bear switch
        if qqq_price > sma_200:
            # Price above 200 SMA: allocate to standard unleveraged index (QQQ)
            return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
        else:
            # Price below 200 SMA: retreat to safety and earn interest yield (CASH)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class ComposerSMATechAITiltStrategy(BaseStrategy):
    """Composer SMA: Tech/AI-Tilted Hybrid.
    
    If the close price of QQQ is above its 200-day Simple Moving Average (SMA), 
    allocate a blended Tech/AI leveraged basket:
    - 40% QLD (2x Leverage)
    - 30% TQQQ (3x Leverage)
    - 30% QQQ (1x Leverage)
    This results in a combined effective leverage of approximately 2.0x.
    
    Otherwise, de-leverage completely to 100% CASH (earning interest yield).
    
    This strategy balances aggressive bull-market returns with risk moderation 
    via leverage diversification, then sweeps to cash protection in downtrends.
    """

    @property
    def name(self) -> str:
        return "Composer SMA: Tech/AI-Tilted Hybrid"

    @property
    def description(self) -> str:
        return "stateless QQQ > 200 SMA switch between a blended Tech/AI basket (~1.7x leverage) and high-yield CASH."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        # Extract underlying price and indicators
        qqq_price = market_data["QQQ"]
        sma_200 = market_data.get("SMA_200")

        # Default to CASH if indicators not ready
        if sma_200 is None or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        # Check trend: Bull vs Bear switch
        if qqq_price > sma_200:
            # Tech/AI-tilted basket during uptrends:
            # Blended leverage is (0.3 * 1.0) + (0.4 * 2.0) + (0.3 * 3.0) = 2.0x leverage.
            return {"QQQ": 0.30, "QLD": 0.40, "TQQQ": 0.30, "CASH": 0.0}
        else:
            # Price below 200 SMA: retreat to safety and earn interest yield (CASH)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

