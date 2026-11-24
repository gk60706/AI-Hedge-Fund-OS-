"""自动调仓引擎 (V3.3)

当前持仓 vs 目标持仓 → 差异 → 交易成本 → 生成 BUY/SELL 订单。
"""
from __future__ import annotations

from typing import Any

from portfolio.transaction_cost import TransactionCostModel


class Rebalancer:
    """成本感知的调仓订单生成器。

    调仓幅度低于 min_trade_weight 的股票不交易，
    其余按目标-当前权重差生成 BUY/SELL 订单。
    """

    def __init__(self, min_trade_weight: float = 0.02):
        self.min_trade_weight = min_trade_weight
        self.cost_model = TransactionCostModel()

    def generate_orders(
        self,
        current_positions: dict[str, float],
        target_positions: dict[str, float],
        prices: dict[str, float],
        total_equity: float,
    ) -> list[dict[str, Any]]:
        """生成调仓订单列表。

        :param current_positions: 代码 -> 当前权重。
        :param target_positions: 代码 -> 目标权重。
        :param prices: 代码 -> 当前价格。
        :param total_equity: 总资产。
        :return: 订单列表（按交易金额降序）。
        """
        orders = []
        codes = set(current_positions) | set(target_positions)
        for code in codes:
            current_weight = current_positions.get(code, 0.0)
            target_weight = target_positions.get(code, 0.0)
            delta = target_weight - current_weight

            # 调仓幅度太小，不交易
            if abs(delta) < self.min_trade_weight:
                continue

            trade_value = abs(delta) * total_equity
            side = "BUY" if delta > 0 else "SELL"
            price = prices.get(code, 0.0)
            if price <= 0:
                continue

            cost = self.cost_model.estimate(
                trade_value=trade_value,
                side=side,
            )
            orders.append(
                {
                    "code": code,
                    "side": side,
                    "current_weight": current_weight,
                    "target_weight": target_weight,
                    "delta_weight": delta,
                    "trade_value": trade_value,
                    "estimated_cost": cost,
                    "price": price,
                }
            )

        orders.sort(
            key=lambda x: abs(x["trade_value"]),
            reverse=True,
        )
        return orders
