"""V2.9 AI 多 Agent 投资委员会：最终决策对象。"""
from __future__ import annotations

from typing import Any


class InvestmentDecision:
    def build(
        self,
        code: str,
        committee_result: dict[str, Any],
        allocation: dict[str, Any],
    ) -> dict[str, Any]:
        committee = committee_result["committee"]
        decision = committee["decision"]
        return {
            "code": code,
            "decision": decision,
            "weighted_score": committee["weighted_score"],
            "position_ratio": allocation["position_ratio"],
            "position_value": allocation["position_value"],
            "votes": committee["votes"],
            "agent_analysis": committee_result["agents"],
        }
