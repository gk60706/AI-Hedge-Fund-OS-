"""换手率控制 (V3.4)

Turnover = Σ|target - current|，限制每日最大换手。
"""
from __future__ import annotations


class TurnoverController:
    """换手率控制器，防止因 Alpha 微小变化而频繁交易。"""

    def __init__(self, max_turnover: float = 0.30):
        self.max_turnover = max_turnover

    def calculate_turnover(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> float:
        """计算组合换手率（目标-当前权重差绝对值之和）。"""
        codes = set(current_weights) | set(target_weights)
        turnover = 0.0
        for code in codes:
            current = current_weights.get(code, 0.0)
            target = target_weights.get(code, 0.0)
            turnover += abs(target - current)
        return turnover

    def allowed(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> bool:
        """换手是否在允许范围内。"""
        turnover = self.calculate_turnover(
            current_weights,
            target_weights,
        )
        return turnover <= self.max_turnover
