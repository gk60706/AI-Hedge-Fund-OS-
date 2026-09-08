"""V0.2 Quant Agent：技术分析（20 日均线）。"""
from __future__ import annotations

from agents.models import AgentResult


def quant_agent(history) -> AgentResult:
    close = history["收盘"].dropna()
    if close.empty:
        return AgentResult(
            agent="Quant",
            score=50,
            opinion="历史数据不足",
            risks=["历史数据不足"],
        )
    ma20 = close.rolling(20).mean().iloc[-1]
    price = close.iloc[-1]
    score = 50
    risks: list[str] = []
    if price > ma20:
        score += 20
        opinion = "价格站上20日均线"
    else:
        score -= 20
        opinion = "跌破20日均线"
        risks.append("趋势偏弱")
    return AgentResult(
        agent="Quant",
        score=score,
        opinion=opinion,
        risks=risks,
    )
