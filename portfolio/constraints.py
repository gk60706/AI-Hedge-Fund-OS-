"""V3.1 组合约束：单票上限 + 总仓位校验。"""

from __future__ import annotations

from typing import Any


class PortfolioConstraints:
    """组合约束校验器。"""

    def __init__(self, max_single_weight: float = 0.20):
        self.max_single_weight = max_single_weight

    def validate(
        self,
        portfolio: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """校验组合权重是否满足约束。

        Args:
            portfolio: 组合持仓列表（每项含 code / weight）。

        Returns:
            {"valid", "total_weight", "cash_weight", "reason"}。
        """
        total_weight = sum(
            float(p.get("weight", 0.0))
            for p in portfolio
        )
        over = [
            p.get("code", "?")
            for p in portfolio
            if float(p.get("weight", 0.0)) > self.max_single_weight + 1e-9
        ]
        if over:
            return {
                "valid": False,
                "total_weight": round(total_weight, 4),
                "cash_weight": round(max(0.0, 1.0 - total_weight), 4),
                "reason": f"single position over limit: {over}",
            }
        if total_weight > 1.0 + 1e-9:
            return {
                "valid": False,
                "total_weight": round(total_weight, 4),
                "cash_weight": 0.0,
                "reason": "total weight exceeds 1.0",
            }
        return {
            "valid": True,
            "total_weight": round(total_weight, 4),
            "cash_weight": round(max(0.0, 1.0 - total_weight), 4),
            "reason": "OK",
        }
