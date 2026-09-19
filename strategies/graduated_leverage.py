"""4-Tier Graduated Leverage Architecture (TQQQ, QLD, QQQ, and SPAXX).

Addresses the flaw in traditional 3-tier SMA models where holding 1x QQQ during
bear markets produced catastrophic -95% to -97% drawdowns during the Dot-Com crash (2000-2002)
and Global Financial Crisis (2007-2009).

This strategy introduces a stepped de-risking ladder across 4 regimes:
  1. Strong Bull:               Price > 50 SMA AND Price > 200 SMA -> 100% TQQQ (3x leverage)
  2. Bull Pullback:             Price < 50 SMA BUT Price > 200 SMA -> 100% QLD (2x leverage)
  3. Bottoming / Counter-Trend: Price > 50 SMA BUT Price < 200 SMA -> 100% QQQ (1x unleveraged)
  4. Full Bear Market:          Price < 50 SMA AND Price < 200 SMA -> 100% SPAXX (Cash Yield)

Key Design Guardrails:
  - Technical indicators are ALWAYS calculated on unleveraged QQQ daily bars, never on leveraged ETFs.
  - Optional 1% Buffer Rule (Anti-Whipsaw): Uses a hysteresis band around the 50 and 200 SMAs
    to avoid premature whipsaws during sideways consolidations.
  - IRA / Roth IRA Friendly: Rotates into Fidelity's SPAXX government money market sweep in bear regimes,
    earning steady interest yield while fully protecting capital.
"""

from typing import Dict, Optional
import numpy as np
from strategies.base import BaseStrategy


class GraduatedLeverageStrategy(BaseStrategy):
    """4-Tier Graduated Leverage Strategy (TQQQ / QLD / QQQ / SPAXX).

    Evaluates unleveraged QQQ against both its 50-day and 200-day Simple Moving Averages.
    """

    def __init__(self, buffer_pct: float = 0.0) -> None:
        """Initialize strategy.

        Args:
            buffer_pct: Whipsaw buffer percentage (e.g. 0.01 for 1% buffer). Default 0.0.
        """
        self.buffer_pct: float = buffer_pct
        self.state_50: Optional[str] = None    # "ABOVE" or "BELOW"
        self.state_200: Optional[str] = None   # "ABOVE" or "BELOW"

    def reset(self) -> None:
        """Reset internal state for a fresh backtest run."""
        self.state_50 = None
        self.state_200 = None

    @property
    def name(self) -> str:
        if self.buffer_pct > 0:
            return f"4-Tier Graduated Leverage ({self.buffer_pct * 100:.0f}% Buffer)"
        return "4-Tier Graduated Leverage"

    @property
    def description(self) -> str:
        buf_str = f" with {self.buffer_pct * 100:.0f}% buffer" if self.buffer_pct > 0 else ""
        return (
            f"4-tier stepped de-risking{buf_str}: TQQQ (>50 & >200), QLD (<50 & >200), "
            f"QQQ (>50 & <200), and SPAXX (<50 & <200)."
        )

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        """Determine target asset allocation across TQQQ, QLD, QQQ, and SPAXX (CASH).

        Args:
            date: Current Timestamp.
            market_data: Dictionary of prices and indicators.
            portfolio_state: Current portfolio state.

        Returns:
            Dict mapping ticker to allocation weight summing to 1.0.
        """
        qqq_price = market_data.get("QQQ")
        sma_50 = market_data.get("SMA_50")
        sma_200 = market_data.get("SMA_200")

        # Defensive fallback: If indicators are warming up or missing, hold 100% SPAXX (CASH)
        if (
            qqq_price is None
            or sma_50 is None
            or sma_200 is None
            or np.isnan(sma_50)
            or np.isnan(sma_200)
            or np.isnan(qqq_price)
        ):
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}

        buf = self.buffer_pct

        # Determine state relative to 200-day SMA (Macro Anchor)
        if buf > 0:
            if self.state_200 is None:
                self.state_200 = "ABOVE" if qqq_price >= sma_200 else "BELOW"
            else:
                if self.state_200 == "BELOW" and qqq_price > sma_200 * (1.0 + buf):
                    self.state_200 = "ABOVE"
                elif self.state_200 == "ABOVE" and qqq_price < sma_200 * (1.0 - buf):
                    self.state_200 = "BELOW"
        else:
            self.state_200 = "ABOVE" if qqq_price > sma_200 else "BELOW"

        # Determine state relative to 50-day SMA (Intermediate Momentum)
        if buf > 0:
            if self.state_50 is None:
                self.state_50 = "ABOVE" if qqq_price >= sma_50 else "BELOW"
            else:
                if self.state_50 == "BELOW" and qqq_price > sma_50 * (1.0 + buf):
                    self.state_50 = "ABOVE"
                elif self.state_50 == "ABOVE" and qqq_price < sma_50 * (1.0 - buf):
                    self.state_50 = "BELOW"
        else:
            self.state_50 = "ABOVE" if qqq_price > sma_50 else "BELOW"

        # 4-Tier Graduated Allocation Ladder
        if self.state_50 == "ABOVE" and self.state_200 == "ABOVE":
            # Regime 1: Strong Bull -> 100% TQQQ (3x)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
        elif self.state_50 == "BELOW" and self.state_200 == "ABOVE":
            # Regime 2: Bull Pullback -> 100% QLD (2x)
            return {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}
        elif self.state_50 == "ABOVE" and self.state_200 == "BELOW":
            # Regime 3: Bottoming / Counter-Trend Bounce -> 100% QQQ (1x)
            return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
        else:
            # Regime 4: Full Bear Market -> 100% SPAXX (Cash Yield)
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class BufferedGraduatedLeverageStrategy(GraduatedLeverageStrategy):
    """4-Tier Graduated Leverage with 1% Anti-Whipsaw Buffer Rule.

    Requires price to clear the 50-day and 200-day SMAs by at least 1.0% before
    triggering regime transitions, reducing churn in sideways markets.
    """

    def __init__(self, buffer_pct: float = 0.01) -> None:
        super().__init__(buffer_pct=buffer_pct)


# Backwards-compatible aliases
Graduated4TierLeverageStrategy = GraduatedLeverageStrategy
