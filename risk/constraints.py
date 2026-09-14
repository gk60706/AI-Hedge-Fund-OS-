"""风险约束引擎 (V3.4)

单票/行业/Beta/最低现金四类硬约束。
"""
from __future__ import annotations


class RiskConstraintEngine:
    """机构级风险约束检查。"""

    def __init__(
        self,
        max_single_weight: float = 0.20,
        max_industry_weight: float = 0.30,
        max_beta: float = 1.10,
        min_cash: float = 0.05,
    ):
        self.max_single_weight = max_single_weight
        self.max_industry_weight = max_industry_weight
        self.max_beta = max_beta
        self.min_cash = min_cash

    def check_single_stock(self, weight: float) -> bool:
        """单票权重不超过上限。"""
        return weight <= self.max_single_weight

    def check_industry(self, industry_weight: float) -> bool:
        """行业权重不超过上限。"""
        return industry_weight <= self.max_industry_weight

    def check_beta(self, portfolio_beta: float) -> bool:
        """组合 Beta 不超过上限。"""
        return portfolio_beta <= self.max_beta

    def check_cash(self, cash_weight: float) -> bool:
        """现金比例不低于下限。"""
        return cash_weight >= self.min_cash
