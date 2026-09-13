"""V3.0 AI Autonomous Hedge Fund：风险引擎。"""
from __future__ import annotations

from typing import Any


class RiskEngineV30:
    def __init__(
        self,
        max_portfolio_drawdown: float = 0.15,
        max_single_position: float = 0.20,
        max_total_exposure: float = 0.95,
    ):
        self.max_portfolio_drawdown = (
            max_portfolio_drawdown
        )
        self.max_single_position = (
            max_single_position
        )
        self.max_total_exposure = (
            max_total_exposure
        )

    def validate_position(
        self,
        target_weight: float,
    ) -> dict[str, Any]:
        if target_weight <= 0:
            return {
                "allowed": False,
                "reason": "invalid weight",
            }
        if (
            target_weight
            > self.max_single_position
        ):
            return {
                "allowed": False,
                "reason": "single position too large",
            }
        return {
            "allowed": True,
            "reason": "OK",
        }

    def validate_portfolio(
        self,
        weights: dict[str, float],
    ) -> dict[str, Any]:
        total_weight = sum(
            weights.values()
        )
        if (
            total_weight
            > self.max_total_exposure
        ):
            return {
                "allowed": False,
                "reason": "total exposure exceeds limit",
            }
        for code, weight in weights.items():
            result = self.validate_position(weight)
            if not result["allowed"]:
                return {
                    "allowed": False,
                    "reason": f"{code}: " f"{result['reason']}",
                }
        return {
            "allowed": True,
            "reason": "portfolio risk OK",
        }
