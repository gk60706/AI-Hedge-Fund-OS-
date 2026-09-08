"""V0.2 Risk Agent：风险控制。"""
from __future__ import annotations

from agents.models import AgentResult


def risk_agent(stock: dict) -> AgentResult:
    score = 70
    risks: list[str] = []
    change = stock.get("change") or 0
    if change > 9:
        score -= 20
        risks.append("短期涨幅过大")
    return AgentResult(
        agent="Risk",
        score=score,
        opinion="风险模型评分",
        risks=risks,
    )
