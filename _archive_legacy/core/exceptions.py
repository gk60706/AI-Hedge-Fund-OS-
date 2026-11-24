"""V3.9.1 exception hierarchy for the research engine."""


class ResearchError(Exception):
    """Base class for all V3.9.1 research-engine errors."""


class DataError(ResearchError):
    """Raised when raw market / fundamental data cannot be acquired or normalized."""


class ValidationError(ResearchError):
    """Raised when a panel fails data-quality / look-ahead checks."""


class BacktestError(ResearchError):
    """Raised when the backtest cannot be executed."""
