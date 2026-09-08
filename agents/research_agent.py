"""V0.2 Research Agent：基本面研究。"""
from __future__ import annotations

from agents.models import AgentResult


def research_agent(stock: dict) -> AgentResult:
    score = 60
    risks: list[str] = []
    turnover = stock.get("turnover") or 0
    if turnover > 15:
        risks.append("换手率过高")
        score -= 10
    return AgentResult(
        agent="Research",
        score=score,
        opinion="基础面数据待接入财报系统",
        risks=risks,
    )
