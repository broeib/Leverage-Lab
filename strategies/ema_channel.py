"""EMA Channel strategies — ported from the TradingView "PlayBit EMA" indicator.

The indicator draws a channel between the 200-day EMA of the High (top) and the
200-day EMA of the Close (bottom) on the unleveraged 1x ticker, and colours it by
where the close sits:

  - Green (close above the top line):   strong uptrend
  - Gray  (close inside the channel):   transitional / choppy
  - Red   (close below the bottom line): downtrend

Both strategies are stateless (the allocation depends only on today's channel
state), so they translate directly into Composer-style conditional blocks. They
differ only in what they hold while the channel is gray.
"""

from typing import Dict
import numpy as np
from strategies.base import BaseStrategy
from tools.config_loader import get_strategy_params

TQQQ_ALLOC = {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
QLD_ALLOC = {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}
QQQ_ALLOC = {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
CASH_ALLOC = {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


def _valid(x) -> bool:
    return x is not None and not np.isnan(x)


def _channel_state(market_data: dict, top_mult: float = 1.0, bot_mult: float = 1.0) -> str:
    """Return "GREEN", "GRAY", "RED", or "WARMUP" for the current bar.

    ``top_mult`` / ``bot_mult`` widen the channel slightly (e.g. 1.01 / 0.99) so
    that price has to clear the lines by a margin before the zone changes.
    """
    price = market_data["QQQ"]
    top = market_data.get("EMA_TOP")
    bot = market_data.get("EMA_BOT")

    if not _valid(top) or not _valid(bot):
        return "WARMUP"
    if price > top * top_mult:
        return "GREEN"
    if price < bot * bot_mult:
        return "RED"
    return "GRAY"


class EMAChannelAggressiveStrategy(BaseStrategy):
    """PlayBit EMA Channel: 3x in green, 2x in gray, cash in red.

    Keeps moderate leverage on while the trend is merely pausing, and only
    fully de-risks once the close breaks below the EMA of the closes.
    """

    @property
    def name(self) -> str:
        return "EMA Channel: 3x / 2x / Cash"

    @property
    def description(self) -> str:
        return "PlayBit 200 EMA channel: 3x above the High-EMA, 2x inside the channel, high-yield CASH below the Close-EMA."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        state = _channel_state(market_data)

        if state == "GREEN":
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
        if state == "GRAY":
            return {"QQQ": 0.0, "QLD": 1.0, "TQQQ": 0.0, "CASH": 0.0}
        # RED or indicators not ready
        return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class EMAChannelConservativeStrategy(BaseStrategy):
    """PlayBit EMA Channel: 3x in green, 1x in gray, cash in red.

    Drops all leverage as soon as the close falls back inside the channel,
    treating the gray zone as an early warning rather than a pause.
    """

    @property
    def name(self) -> str:
        return "EMA Channel: 3x / 1x / Cash"

    @property
    def description(self) -> str:
        return "PlayBit 200 EMA channel: 3x above the High-EMA, unleveraged 1x inside the channel, high-yield CASH below the Close-EMA."

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        state = _channel_state(market_data)

        if state == "GREEN":
            return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 1.0, "CASH": 0.0}
        if state == "GRAY":
            return {"QQQ": 1.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 0.0}
        # RED or indicators not ready
        return {"QQQ": 0.0, "QLD": 0.0, "TQQQ": 0.0, "CASH": 1.0}


class EMAChannelV2Strategy(BaseStrategy):
    """EMA Channel v2 — the 3x / 2x / Cash ladder with a risk overlay.

    Selected from a ~640-variant sweep across the QQQ, SOXX and SPY universes
    (see ``tools/sweep_ema_channel.py``). Two changes to the base ladder:

    1. Channel buffers: price must clear the High-EMA by +1% to turn green and
       fall 1% below the Close-EMA to turn red, which trims whipsaws.
    2. Risk overlay: while the channel would hold leverage, exposure is capped
       at unleveraged 1x if ANY of these fire on the 1x index:
         - it is more than 15% below its 252-day high (drawdown breaker)
         - it is below its 100-day EMA (trend pause)
         - 20-day realised volatility exceeds 40% annualised (volatility gate)

    Across all three universes the overlay roughly halves max drawdown
    (e.g. NASDAQ-100 80% -> 49%) with no loss of CAGR versus the base ladder.
    All thresholds are read from ``config/strategies.json`` (``ema_channel``).
    """

    def __init__(self) -> None:
        p = get_strategy_params("ema_channel")
        self.top_mult = float(p.get("top_buffer", 1.01))
        self.bot_mult = float(p.get("bot_buffer", 0.99))
        self.dd_breaker = float(p.get("dd_breaker", 0.15))
        self.vol_gate = float(p.get("vol_gate", 40.0))

    @property
    def name(self) -> str:
        return "EMA Channel v2: Risk-Managed"

    @property
    def description(self) -> str:
        return ("PlayBit 200 EMA channel (±1% buffers) 3x / 2x / CASH, capped at 1x when the index is "
                ">15% off its 52-week high, below its 100 EMA, or 20d realised vol > 40%.")

    def get_allocation(self, date, market_data: dict, portfolio_state: dict) -> Dict[str, float]:
        state = _channel_state(market_data, self.top_mult, self.bot_mult)

        if state == "GREEN":
            alloc = TQQQ_ALLOC
        elif state == "GRAY":
            alloc = QLD_ALLOC
        else:  # RED or WARMUP
            return CASH_ALLOC

        # Risk overlay: step down to 1x when any trigger fires
        price = market_data["QQQ"]
        roll_high = market_data.get("ROLL_HIGH")
        ema_fast = market_data.get("EMA_FAST")
        rvol = market_data.get("RVOL")

        fired = (
            (_valid(roll_high) and price < roll_high * (1.0 - self.dd_breaker))
            or (_valid(ema_fast) and price < ema_fast)
            or (_valid(rvol) and rvol > self.vol_gate)
        )
        return QQQ_ALLOC if fired else alloc
