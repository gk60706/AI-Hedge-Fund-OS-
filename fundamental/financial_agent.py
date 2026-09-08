"""V0.4 财报分析 Agent：盈利质量评分。"""
from __future__ import annotations

from agents.models import AgentResult


def financial_agent(financial: dict) -> AgentResult:
    score = 50
    risks: list[str] = []
    roe = financial.get("roe")
    margin = financial.get("gross_margin")
    if roe:
        if roe > 15:
            score += 20
        elif roe < 5:
            score -= 15
            risks.append("ROE偏低")
    if margin:
        if margin > 30:
            score += 15
        elif margin < 10:
            score -= 10
    return AgentResult(
        agent="Financial",
        score=max(0, min(100, score)),
        opinion="盈利质量分析",
        risks=risks,
    )
