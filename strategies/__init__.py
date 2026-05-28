# Strategies package
from strategies.sma_trend import SMATrendStrategy
from strategies.rsi_momentum import RSIMomentumStrategy
from strategies.vix_volatility import VIXVolatilityStrategy
from strategies.bollinger_reversion import BollingerReversionStrategy
from strategies.macd_trend import MACDTrendStrategy
from strategies.drawdown_dynamic import DrawdownDynamicStrategy
from strategies.composite_signal import CompositeSignalStrategy
from strategies.tactical_cash import TacticalCashStrategy
from strategies.enhanced_sma import EnhancedSMATrendStrategy
from strategies.composer_sma import (
    ComposerSMATQQQCashStrategy,
    ComposerSMAQLDCashStrategy,
    ComposerSMAQQQCashStrategy,
    ComposerSMATechAITiltStrategy,
)
from strategies.benchmarks import (
    BuyHoldQQQ,
    BuyHoldQLD,
    BuyHoldTQQQ,
    EqualWeightStatic,
)

ALL_STRATEGIES = [
    SMATrendStrategy,
    RSIMomentumStrategy,
    VIXVolatilityStrategy,
    BollingerReversionStrategy,
    MACDTrendStrategy,
    DrawdownDynamicStrategy,
    CompositeSignalStrategy,
    TacticalCashStrategy,
    EnhancedSMATrendStrategy,
    ComposerSMATQQQCashStrategy,
    ComposerSMAQLDCashStrategy,
    ComposerSMAQQQCashStrategy,
    ComposerSMATechAITiltStrategy,
]

ALL_BENCHMARKS = [
    BuyHoldQQQ,
    BuyHoldQLD,
    BuyHoldTQQQ,
    EqualWeightStatic,
]

