"""V0.2 Decision Agent：多 Agent 综合决策。"""
from __future__ import annotations

from agents.models import AgentResult, InvestmentDecision


def decision_agent(stock: dict, results: list[AgentResult]) -> InvestmentDecision:
    if not results:
        raise ValueError("决策需要至少一个 Agent 评分结果")
    score = sum(x.score for x in results) / len(results)
    if score >= 75:
        action = "BUY"
        position = 0.2
    elif score >= 55:
        action = "HOLD"
        position = 0.1
    else:
        action = "AVOID"
        position = 0
    return InvestmentDecision(
        stock=stock["code"],
        score=score,
        action=action,
        position=position,
        reason="多Agent综合评分",
    )
