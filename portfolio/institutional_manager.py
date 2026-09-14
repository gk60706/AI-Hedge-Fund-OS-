"""机构级组合管理器 (V3.4)

Ensemble 优化 → 流动性约束 → 仓位换算 → 调仓订单。
"""
from __future__ import annotations

from portfolio.position_sizer import PositionSizer
from portfolio.liquidity import LiquidityConstraint
from portfolio.turnover import TurnoverController
from portfolio.rebalancer import Rebalancer


class InstitutionalPortfolioManager:
    """V3.4 机构级组合引擎。"""

    def __init__(self):
        self.optimizer = None
        self.position_sizer = PositionSizer()
        self.liquidity = LiquidityConstraint(
            max_participation=0.10,
        )
        self.turnover = TurnoverController(
            max_turnover=0.30,
        )
        self.rebalancer = Rebalancer(
            min_trade_weight=0.02,
        )

    def apply_liquidity_constraint(
        self,
        weights: dict[str, float],
        liquidity: dict[str, float],
        total_equity: float,
    ) -> dict[str, float]:
        """逐票施加流动性上限并重新归一化。

        :param weights: 目标权重。
        :param liquidity: 代码 -> 日均成交额。
        :param total_equity: 总资产。
        :return: 流动性约束后的权重。
        """
        result = {}
        for code, weight in weights.items():
            avg_amount = liquidity.get(code, 0.0)
            max_weight = self.liquidity.allowed_weight(
                total_equity,
                avg_amount,
            )
            result[code] = min(weight, max_weight)

        total = sum(result.values())
        if total > 0:
            result = {
                code: weight / total
                for code, weight in result.items()
            }
        return result

    def size_positions(
        self,
        weights: dict[str, float],
        prices: dict[str, float],
        total_equity: float,
    ) -> dict[str, dict]:
        """将目标权重换算为整数手仓位。

        :return: 代码 -> {"shares", "value", "actual_weight"}。
        """
        result = {}
        for code, weight in weights.items():
            price = prices.get(code, 0.0)
            result[code] = self.position_sizer.calculate(
                total_equity,
                weight,
                price,
            )
        return result
