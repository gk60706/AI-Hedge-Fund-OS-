"""BUY / SELL / HOLD 决策 (V3.3)

基于净 Alpha（预期 Alpha - 交易成本）决定是否调仓。
"""
from __future__ import annotations


class RebalanceDecisionEngine:
    """调仓决策引擎。

    净 Alpha = 预期 Alpha - 估计成本；
    > min_expected_alpha → BUY；< -min_expected_alpha → SELL；否则 HOLD。
    """

    def __init__(self, min_expected_alpha: float = 0.02):
        self.min_expected_alpha = min_expected_alpha

    def decide(
        self,
        expected_alpha: float,
        estimated_cost: float,
    ) -> str:
        """返回 BUY / SELL / HOLD。"""
        net_alpha = expected_alpha - estimated_cost
        if net_alpha > self.min_expected_alpha:
            return "BUY"
        if net_alpha < -self.min_expected_alpha:
            return "SELL"
        return "HOLD"
