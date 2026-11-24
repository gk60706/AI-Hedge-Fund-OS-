"""流动性约束 (V3.4)

单票最大交易金额 = 日均成交额 × 参与率。
"""
from __future__ import annotations


class LiquidityConstraint:
    """基于日成交额的流动性约束。"""

    def __init__(self, max_participation: float = 0.10):
        self.max_participation = max_participation

    def max_trade_value(
        self,
        average_daily_amount: float,
    ) -> float:
        """单票最大可交易金额。"""
        return average_daily_amount * self.max_participation

    def allowed_weight(
        self,
        total_equity: float,
        average_daily_amount: float,
    ) -> float:
        """单票允许的最大权重。"""
        if total_equity <= 0:
            return 0.0
        maximum_trade = self.max_trade_value(
            average_daily_amount,
        )
        return maximum_trade / total_equity
