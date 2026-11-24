"""V3.0.6 AI 自动淘汰策略：策略退役引擎。"""
from __future__ import annotations

from typing import Any

from strategy_lab.strategy_health import (
    StrategyHealth,
)


class StrategyRetirementEngine:
    def __init__(
        self,
        min_health_score: float = 40,
        max_drawdown: float = -0.30,
        min_sharpe: float = 0.0,
    ):
        self.min_health_score = min_health_score
        self.max_drawdown = max_drawdown
        self.min_sharpe = min_sharpe

    def should_retire(
        self,
        metrics: dict[str, Any],
        health: dict[str, Any],
    ) -> bool:
        if health["health_score"] < self.min_health_score:
            return True
        if metrics.get("max_drawdown", 0) < self.max_drawdown:
            return True
        if metrics.get("sharpe", 0) < self.min_sharpe:
            return True
        return False

    def process(self, strategy):
        metrics = strategy.metrics
        health = StrategyHealth().evaluate(metrics)
        if self.should_retire(metrics, health):
            strategy.status = "RETIRED"
        else:
            strategy.status = health["status"]
        return strategy, health
