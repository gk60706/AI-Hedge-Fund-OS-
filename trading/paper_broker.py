"""V3.0 AI Autonomous Hedge Fund：模拟券商（Paper Broker）。

V3.0 暂时绝对不接真实券商，先建立模拟券商。
"""
from __future__ import annotations

import uuid

from portfolio.portfolio import PortfolioV30 as Portfolio
from portfolio.position import PositionV30 as Position
from trading.order import (
    OrderV30 as Order,
    OrderSideV30 as OrderSide,
)


class PaperBrokerV30:
    def __init__(
        self,
        portfolio: Portfolio,
        commission: float = 0.0003,
        slippage: float = 0.0005,
    ):
        self.portfolio = portfolio
        self.commission = commission
        self.slippage = slippage

    def submit_order(
        self,
        code: str,
        name: str,
        side: OrderSide,
        quantity: int,
        price: float,
    ) -> Order:
        order = Order(
            code=code,
            side=side,
            quantity=quantity,
            price=price,
            order_id=str(
                uuid.uuid4()
            ),
        )
        if quantity <= 0:
            order.status = "REJECTED"
            return order
        if side == OrderSide.BUY:
            execution_price = (
                price
                * (
                    1
                    + self.slippage
                )
            )
            cost = (
                execution_price
                * quantity
            )
            fee = (
                cost
                * self.commission
            )
            total_cost = cost + fee
            if (
                total_cost
                > self.portfolio.cash
            ):
                order.status = "REJECTED"
                return order
            self.portfolio.cash -= (
                total_cost
            )
            if code in self.portfolio.positions:
                position = (
                    self.portfolio.positions[code]
                )
                old_value = (
                    position.avg_price
                    * position.shares
                )
                new_value = (
                    execution_price
                    * quantity
                )
                total_shares = (
                    position.shares
                    + quantity
                )
                position.avg_price = (
                    old_value
                    + new_value
                ) / total_shares
                position.shares = (
                    total_shares
                )
                position.current_price = (
                    execution_price
                )
            else:
                self.portfolio.add_position(
                    Position(
                        code=code,
                        name=name,
                        shares=quantity,
                        avg_price=execution_price,
                        current_price=execution_price,
                    )
                )
        else:
            if code not in self.portfolio.positions:
                order.status = "REJECTED"
                return order
            position = (
                self.portfolio.positions[code]
            )
            quantity = min(
                quantity,
                position.shares,
            )
            execution_price = (
                price
                * (
                    1
                    - self.slippage
                )
            )
            revenue = (
                execution_price
                * quantity
            )
            fee = (
                revenue
                * self.commission
            )
            self.portfolio.cash += (
                revenue
                - fee
            )
            position.shares -= quantity
            if position.shares == 0:
                self.portfolio.remove_position(
                    code
                )
        order.status = "FILLED"
        self.portfolio.trade_history.append({
            "order_id": order.order_id,
            "code": code,
            "side": side.value,
            "quantity": quantity,
            "price": price,
            "status": order.status,
        })
        return order
