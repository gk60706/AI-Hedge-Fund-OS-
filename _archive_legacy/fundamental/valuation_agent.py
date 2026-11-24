"""V0.4 巴菲特估值 Agent。"""
from __future__ import annotations

from agents.models import AgentResult


def valuation_agent(financial: dict) -> AgentResult:
    score = 50
    pe = financial.get("pe")
    if pe:
        if pe < 30:
            score += 20
        elif pe > 80:
            score -= 20
    return AgentResult(
        agent="Valuation",
        score=max(0, min(100, score)),
        opinion="价值估值分析",
        risks=[],
    )
