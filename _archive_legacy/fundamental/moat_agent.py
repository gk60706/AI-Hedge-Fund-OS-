"""V0.4 企业护城河 Agent。"""
from __future__ import annotations

from agents.models import AgentResult

_KEYWORDS = ["龙头", "专利", "技术壁垒", "市场份额"]


def moat_agent(company: str) -> AgentResult:
    score = 50
    risks: list[str] = []
    for k in _KEYWORDS:
        if k in company:
            score += 10
    return AgentResult(
        agent="Moat",
        score=min(score, 100),
        opinion="企业护城河评分",
        risks=risks,
    )
