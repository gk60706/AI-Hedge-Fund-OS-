"""V3.0 AI Autonomous Hedge Fund：执行引擎。"""
from __future__ import annotations

from typing import Any

from trading.order import OrderSideV30 as OrderSide
from trading.paper_broker import PaperBrokerV30 as PaperBroker


class ExecutionEngineV30:
    def __init__(
        self,
        broker: PaperBroker,
    ):
        self.broker = broker

    def execute_targets(
        self,
        targets: list[dict[str, Any]],
        prices: dict[str, float],
        names: dict[str, str],
    ) -> list:
        results = []
        portfolio_value = (
            self.broker.portfolio.total_value
        )
        for target in targets:
            code = target["code"]
            weight = target["target_weight"]
            price = prices.get(code)
            if price is None:
                continue
            target_value = (
                portfolio_value
                * weight
            )
            quantity = int(
                target_value
                / price
                / 100
            ) * 100
            if quantity <= 0:
                continue
            order = (
                self.broker.submit_order(
                    code=code,
                    name=names.get(code, code),
                    side=OrderSide.BUY,
                    quantity=quantity,
                    price=price,
                )
            )
            results.append(order)
        return results
