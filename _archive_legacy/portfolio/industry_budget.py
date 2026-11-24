"""V3.2 行业风险预算：限制行业集中度。"""

from __future__ import annotations

from collections import defaultdict


class IndustryRiskBudget:
    """行业集中度限制。

    示例：
        AI产业链 ≤ 30%、新能源 ≤ 25%、金融 ≤ 20%、消费 ≤ 20%、其他 ≤ 30%。
    """

    def __init__(self, default_max_weight: float = 0.30):
        self.default_max_weight = default_max_weight

    def apply(
        self,
        weights: dict[str, float],
        industries: dict[str, str],
    ) -> dict[str, float]:
        """对超限行业整体等比缩仓。

        Args:
            weights: {code: weight}。
            industries: {code: industry}。

        Returns:
            调整后的 {code: weight}。
        """
        industry_weights = defaultdict(float)
        for code, weight in weights.items():
            industry = industries.get(code, "UNKNOWN")
            industry_weights[industry] += weight

        result = dict(weights)
        for industry, total_weight in industry_weights.items():
            if total_weight <= self.default_max_weight:
                continue
            scale = self.default_max_weight / total_weight
            for code in result:
                if industries.get(code, "UNKNOWN") == industry:
                    result[code] *= scale
        return result
