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


# ---------------------------------------------------------------------------
# V1.0 量化 Agent（委员会架构版）：基于 Alpha 因子评分。
# 与上方 V0.2 的 quant_agent 函数并存，不删除已有功能。
# ---------------------------------------------------------------------------
class QuantAgent:
    """V1.0 QuantAgent（与 core.agent.BaseAgent 接口兼容的轻量版）。"""

    def __init__(self, name):
        self.name = name

    def run(self, stock):
        alpha = stock.get("alpha", 50)
        return {
            "agent": self.name,
            "score": alpha,
            "reason": "Alpha因子分析",
        }

