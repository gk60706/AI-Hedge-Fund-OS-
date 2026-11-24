"""V0.4 行业景气 Agent。"""
from __future__ import annotations

from agents.models import AgentResult

_HOT_WORDS = ["AI", "半导体", "新能源", "机器人"]


def industry_agent(industry: str) -> AgentResult:
    score = 50
    for word in _HOT_WORDS:
        if word in industry:
            score += 10
    return AgentResult(
        agent="Industry",
        score=min(score, 100),
        opinion="行业景气分析",
        risks=[],
    )
