"""Global constants used across the backtesting engine and strategies."""

# Time conventions
TRADING_DAYS_PER_YEAR: int = 252
WEEKS_PER_YEAR: int = 52

# Default backtesting parameters
DEFAULT_WEEKLY_CONTRIBUTION: float = 5000.0
DEFAULT_SLIPPAGE: float = 0.001
CASH_YIELD_ANNUAL: float = 0.045
RISK_FREE_RATE_ANNUAL: float = 0.04

# Valid ETF/Asset tickers in the system
VALID_TICKERS = {"QQQ", "QLD", "TQQQ", "CASH"}
