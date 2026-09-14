"""V3.6 TradingCostModel：交易成本模型（佣金最低 5 元 / 印花税 / 滑点）。"""

from __future__ import annotations


class TradingCostModel:
    def __init__(
        self,
        commission_rate=0.0003,
        stamp_duty_rate=0.0005,
        slippage_rate=0.0005,
        minimum_commission=5.0,
    ):
        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.slippage_rate = slippage_rate
        self.minimum_commission = minimum_commission

    def commission(self, value: float) -> float:
        if value <= 0:
            return 0.0
        return max(value * self.commission_rate, self.minimum_commission)

    def stamp_duty(self, sell_value: float) -> float:
        if sell_value <= 0:
            return 0.0
        return sell_value * self.stamp_duty_rate

    def buy_price(self, price: float) -> float:
        return price * (1 + self.slippage_rate)

    def sell_price(self, price: float) -> float:
        return price * (1 - self.slippage_rate)
