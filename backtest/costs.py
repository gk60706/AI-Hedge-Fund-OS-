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
# ============================================================================
# V3.9.1 unified research engine - transaction cost (notional, side, dump)
# ============================================================================


def transaction_cost(
    notional: float,
    side: str,
    commission_rate=0.0003,
    stamp_duty=0.0005,
    min_commission=5.0,
):
    notional = abs(float(notional))
    if notional <= 0:
        return 0.0
    commission = max(min_commission, notional * commission_rate)
    stamp = notional * stamp_duty if side.upper() == "SELL" else 0.0
    return commission + stamp


# ============================================================================
# V3.9.2 frozen TransactionCostModel + build_cost_model (Alpha Research Engine)
# ============================================================================
from dataclasses import dataclass


@dataclass(frozen=True)
class TransactionCostModel:
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.0005
    transfer_fee_rate: float = 0.00001
    slippage_buy: float = 0.0005
    slippage_sell: float = 0.0005
    min_commission: float = 5.0

    def commission(self, value):
        value = max(float(value), 0)
        return 0.0 if value == 0 else max(value * self.commission_rate, self.min_commission)

    def stamp_duty(self, value):
        return max(float(value), 0) * self.stamp_duty_rate

    def transfer_fee(self, value):
        return max(float(value), 0) * self.transfer_fee_rate

    def slippage_cost(self, buy_value=0, sell_value=0):
        return max(float(buy_value), 0) * self.slippage_buy + max(float(sell_value), 0) * self.slippage_sell

    def calculate(self, buy_value=0, sell_value=0):
        b = max(float(buy_value), 0); s = max(float(sell_value), 0); t = b + s
        c = self.commission(t) if t else 0.0
        sd = self.stamp_duty(s); tf = self.transfer_fee(t); sl = self.slippage_cost(b, s)
        return {"buy_value": b, "sell_value": s, "turnover_value": t, "commission": c,
                "stamp_duty": sd, "transfer_fee": tf, "slippage": sl, "total_cost": c + sd + tf + sl}


def build_cost_model(config=None):
    c = config or {}; cm = c.get("commission", {}); sd = c.get("stamp_duty", {})
    tf = c.get("transfer_fee", {}); sl = c.get("slippage", {})
    return TransactionCostModel(
        float(cm.get("rate", .0003)),
        float(sd.get("sell_rate", .0005)),
        float(tf.get("rate", .00001)),
        float(sl.get("buy", .0005)),
        float(sl.get("sell", .0005)),
        float(cm.get("min_fee", 5)),
    )

