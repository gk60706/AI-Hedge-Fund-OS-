"""V0.4 新闻舆情 Agent：关键词情绪打分。"""
from __future__ import annotations

from agents.models import AgentResult

_POSITIVE = ["增长", "订单", "突破", "合作"]
_NEGATIVE = ["处罚", "亏损", "减持", "风险"]


def news_agent(news: str) -> AgentResult:
    score = 50
    risks: list[str] = []
    for word in _POSITIVE:
        if word in news:
            score += 5
    for word in _NEGATIVE:
        if word in news:
            score -= 8
            risks.append(word)
    return AgentResult(
        agent="News",
        score=max(0, min(score, 100)),
        opinion="新闻情绪分析",
        risks=risks,
    )
