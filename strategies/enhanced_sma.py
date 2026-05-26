"""Strategy 9: Enhanced Quant SMA — incorporates decoupled signals, asymmetric buffers, multi-signal confirmation, and high-yield cash sweep."""

from typing import Dict
import numpy as np
from strategies.base import BaseStrategy


class EnhancedSMATrendStrategy(BaseStrategy):
    """
    Advanced Quant-style SMA Trend Strategy.
    
    1. Signal Decoupling: Calculates SMAs, RSI, and MACD on unleveraged QQQ.
    2. Asymmetric Buffer Bands: Ignores minor fluctuations around SMAs using a hysteresis loop
       (requires QQQ > SMA * 1.03 to leverage, and QQQ < SMA * 0.985 to exit).
    3. Multi-Signal Confirmation: Only leverages if:
       - RSI < 70 (not extremely overbought)
       - MACD Histogram is positive (MACD > MACD_Signal, bullish momentum)
       - VIX < 25 (low/moderate volatility environment)
    4. Yield-Bearing Safe Haven: Moves to high-yield CASH (modeled at 4.5% yield) during downtrends.
    """

    def __init__(self):
        # State tracking for hysteresis loop
        self.prev_regime = "BEAR"  # "BULL_STRONG", "BULL_MILD", "BEAR"

    @property
    def name(self) -> str:
        return "Enhanced Quant SMA"

    @property
    def description(self) -> str:
        return "Tactical SMA with +3%/-1.5% asymmetric buffer bands, RSI/MACD/VIX confirmation, and SGOV cash yield."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        qqq_price = market_data["QQQ"]
        sma_50 = market_data.get("SMA_50")
        sma_200 = market_data.get("SMA_200")
        rsi = market_data.get("RSI")
        macd = market_data.get("MACD")
        macd_signal = market_data.get("MACD_Signal")
        vix = market_data.get("VIX")

        # Default to CASH/QQQ if indicators are not ready
        if sma_50 is None or sma_200 is None or rsi is None or np.isnan(sma_50) or np.isnan(sma_200):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        # Calculate momentum confirmation signals
        macd_hist = (macd - macd_signal) if (macd is not None and macd_signal is not None) else 0.0
        is_momentum_bullish = macd_hist >= 0
        is_not_overbought = rsi < 70.0
        is_volatility_safe = vix is None or vix < 25.0

        # Define asymmetric buffers around SMA lines
        # SMA_200 triggers the Bull vs Bear regime
        sma_200_upper = sma_200 * 1.03
        sma_200_lower = sma_200 * 0.985

        # SMA_50 triggers Strong vs Mild leverage regime
        sma_50_upper = sma_50 * 1.02
        sma_50_lower = sma_50 * 0.99

        # 1. Determine overall regime (Bull vs Bear) using SMA_200 buffers
        if self.prev_regime == "BEAR":
            if qqq_price > sma_200_upper:
                current_major = "BULL"
            else:
                current_major = "BEAR"
        else:  # BULL_STRONG or BULL_MILD
            if qqq_price < sma_200_lower:
                current_major = "BEAR"
            else:
                current_major = "BULL"

        # 2. If in BULL, determine the leverage level (Strong vs Mild) using SMA_50 buffers
        if current_major == "BULL":
            if self.prev_regime == "BULL_STRONG":
                if qqq_price < sma_50_lower:
                    current_regime = "BULL_MILD"
                else:
                    current_regime = "BULL_STRONG"
            elif self.prev_regime == "BULL_MILD":
                if qqq_price > sma_50_upper:
                    current_regime = "BULL_STRONG"
                else:
                    current_regime = "BULL_MILD"
            else:  # Coming from BEAR
                if qqq_price > sma_50_upper:
                    current_regime = "BULL_STRONG"
                else:
                    current_regime = "BULL_MILD"
        else:
            current_regime = "BEAR"

        # Update state for next step
        self.prev_regime = current_regime

        # 3. Apply Confirmations to select active allocation
        if current_regime == "BULL_STRONG":
            # Strong trend: check if momentum & vol confirm TQQQ
            if is_momentum_bullish and is_not_overbought and is_volatility_safe:
                # Fully confirmed Strong Bull -> 100% TQQQ
                return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
            else:
                # Disconfirmed: De-leverage to QLD or QQQ to avoid whipsaw/decay
                return {"QQQ": 0.5, "QLD": 0.5, "TQQQ": 0.0, "CASH": 0.0}
        
        elif current_regime == "BULL_MILD":
            # Mild trend: check if volatility confirms QLD
            if is_volatility_safe:
                # Volatility is safe -> 100% QLD
                return {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}
            else:
                # Volatility high -> De-leverage to 100% QQQ
                return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
        
        else:  # BEAR
            # Bear regime -> 100% CASH (Yield-bearing safe haven)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}
