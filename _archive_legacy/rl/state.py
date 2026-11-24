"""V1.7 交易状态定义。"""

from dataclasses import dataclass


@dataclass
class MarketState:
    """市场状态向量。"""

    price: float
    return_1d: float
    return_5d: float
    volatility: float
    volume_ratio: float
    momentum: float
    position: float
    cash_ratio: float

    def to_vector(self):
        return [
            self.return_1d,
            self.return_5d,
            self.volatility,
            self.volume_ratio,
            self.momentum,
            self.position,
            self.cash_ratio,
        ]
