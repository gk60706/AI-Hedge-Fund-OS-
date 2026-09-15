"""V3.6 ExecutionEngine：交易执行器（组合优化与交易执行彻底分开）。

Portfolio Optimizer 只回答：我要多少仓位？
Execution Engine 只回答：实际怎么买？
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionResult:
    shares: int
    cash_change: float
    fee: float
    stamp_duty: float
    executed: bool
    reason: str


class ExecutionEngine:
    def __init__(self, cost_model, lot_size=100):
        self.cost_model = cost_model
        self.lot_size = lot_size

    def buy(
        self,
        cash: float,
        price: float,
        target_value: float,
        limit_up: bool = False,
    ) -> ExecutionResult:
        if limit_up:
            return ExecutionResult(0, 0.0, 0.0, 0.0, False, "LIMIT_UP")

        execution_price = self.cost_model.buy_price(price)
        shares = int(target_value / execution_price / self.lot_size) * self.lot_size
        if shares <= 0:
            return ExecutionResult(0, 0.0, 0.0, 0.0, False, "INSUFFICIENT_VALUE")

        gross = shares * execution_price
        fee = self.cost_model.commission(gross)
        total = gross + fee

        if total > cash:
            shares = int(cash / (execution_price * 1.0003) / self.lot_size) * self.lot_size
            gross = shares * execution_price
            fee = self.cost_model.commission(gross)
            total = gross + fee
            if shares <= 0:
                return ExecutionResult(0, 0.0, 0.0, 0.0, False, "NO_CASH")

        return ExecutionResult(shares, -total, fee, 0.0, True, "BUY")

    def sell(
        self,
        shares: int,
        price: float,
        limit_down: bool = False,
    ) -> ExecutionResult:
        if shares <= 0:
            return ExecutionResult(0, 0.0, 0.0, 0.0, False, "NO_POSITION")
        if limit_down:
            return ExecutionResult(0, 0.0, 0.0, 0.0, False, "LIMIT_DOWN")

        execution_price = self.cost_model.sell_price(price)
        gross = shares * execution_price
        fee = self.cost_model.commission(gross)
        stamp = self.cost_model.stamp_duty(gross)
        net = gross - fee - stamp
        return ExecutionResult(shares, net, fee, stamp, True, "SELL")


# ============================================================================
# V3.9.1 unified research engine - simple order execution
# ============================================================================


@dataclass
class ExecutionResultV391:
    shares: int = 0
    price: float = 0.0
    notional: float = 0.0
    executed: bool = False
    reason: str = ""


def execute_order(
    price: float,
    cash: float,
    lot_size: int = 100,
    slippage: float = 0.0005,
) -> ExecutionResultV391:
    if price <= 0:
        return ExecutionResultV391(reason="invalid_price")
    fill_price = price * (1 + slippage)
    shares = int(cash // (fill_price * lot_size)) * lot_size
    if shares <= 0:
        return ExecutionResultV391(reason="insufficient_cash")
    return ExecutionResultV391(
        shares=shares,
        price=fill_price,
        notional=shares * fill_price,
        executed=True,
    )
