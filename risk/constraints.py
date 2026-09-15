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


# ============================================================================
# V3.9.1 unified research engine - risk constraints dataclass
# ============================================================================

from dataclasses import dataclass  # noqa: E402


@dataclass
class RiskConstraints:
    max_single_weight: float = 0.20
    max_total_exposure: float = 0.95
    min_cash: float = 0.05
    max_leverage: float = 1.0

    def validate(self, weights, cash_ratio: float) -> list:
        errors = []
        weights = list(weights)
        if weights:
            worst = max(weights)
            if worst > self.max_single_weight:
                errors.append(
                    f"单票权重 {worst:.4f} 超过上限 {self.max_single_weight}"
                )
        total = sum(weights)
        if total > self.max_total_exposure:
            errors.append(
                f"总敞口 {total:.4f} 超过上限 {self.max_total_exposure}"
            )
        if cash_ratio < self.min_cash:
            errors.append(
                f"现金比例 {cash_ratio:.4f} 低于下限 {self.min_cash}"
            )
        return errors
