"""V3.0.6 AI 自动淘汰策略：策略健康度评分。"""
from __future__ import annotations

from typing import Any


class StrategyHealth:
    def evaluate(
        self,
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        score = 100
        reasons = []
        sharpe = float(metrics.get("sharpe", 0))
        max_dd = float(metrics.get("max_drawdown", 0))
        win_rate = float(metrics.get("win_rate", 0))
        total_return = float(metrics.get("total_return", 0))
        if sharpe < 0:
            score -= 30
            reasons.append("Sharpe小于0")
        elif sharpe < 0.5:
            score -= 15
            reasons.append("Sharpe偏低")
        if max_dd < -0.30:
            score -= 35
            reasons.append("最大回撤过大")
        elif max_dd < -0.20:
            score -= 20
            reasons.append("最大回撤较高")
        if win_rate < 0.40:
            score -= 15
            reasons.append("胜率偏低")
        if total_return < 0:
            score -= 20
            reasons.append("总收益为负")
        score = max(0, min(100, score))
        if score < 40:
            status = "RETIRED"
        elif score < 60:
            status = "UNDERPERFORM"
        elif score < 80:
            status = "WATCH"
        else:
            status = "HEALTHY"
        return {
            "health_score": score,
            "status": status,
            "reasons": reasons,
        }
