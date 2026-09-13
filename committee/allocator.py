"""V2.9 AI 多 Agent 投资委员会：仓位分配器。"""
from __future__ import annotations


class PositionAllocator:
    def allocate(
        self,
        decision: str,
        risk_score: float,
        portfolio_value: float,
        max_position: float = 0.20,
    ) -> dict:
        if decision == "SELL":
            return {
                "position_ratio": 0.0,
                "position_value": 0.0,
            }
        if decision == "HOLD":
            return {
                "position_ratio": 0.0,
                "position_value": 0.0,
            }
        risk_score = max(0, min(100, risk_score))
        risk_multiplier = (risk_score / 100)
        position_ratio = (max_position * risk_multiplier)
        position_value = (portfolio_value * position_ratio)
        return {
            "position_ratio": round(position_ratio, 4),
            "position_value": round(position_value, 2),
        }
