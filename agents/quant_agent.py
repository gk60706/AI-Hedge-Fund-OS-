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
# V1.3 追加：继承 InvestmentManager 并提供 analyze()（策略竞技场接口），
# run()（V1.0 委员会接口）保持不变。
# ---------------------------------------------------------------------------
from agents.base_manager import InvestmentManager


class QuantAgent(InvestmentManager):
    """V1.0 QuantAgent（与 core.agent.BaseAgent 接口兼容的轻量版）。

    - ``run(stock)``：V1.0 委员会接口，返回 {"agent", "score", "reason"}
    - ``analyze(stock)``：V1.3 竞技场接口，返回 {"manager", "style", "score"}
    """

    def __init__(self, name):
        super().__init__(name)

    def run(self, stock):
        alpha = stock.get("alpha", 50)
        return {
            "agent": self.name,
            "score": alpha,
            "reason": "Alpha因子分析",
        }

    def analyze(self, stock: dict) -> dict:
        alpha = stock.get("alpha", 50)
        return {
            "manager": self.name,
            "style": "QUANT",
            "score": alpha,
        }


# ---------------------------------------------------------------------------
# V2.0 量化策略 Agent（多智能体基金经理系统）：按技术指标/因子打分给出
# BUY/SELL/HOLD。与 V0.2 的 quant_agent 函数、V1.0/V1.3 的 QuantAgent 类
# 并存（旧 QuantAgent 接口为 run()/analyze(stock)，故 V2.0 版以
# QuantAgentV20 命名，不破坏已有接口）。
# ---------------------------------------------------------------------------
class QuantAgentV20:
    """V2.0 量化信号 Agent。"""

    def analyze(self, features: dict) -> str:
        """按因子打分给出 BUY / SELL / HOLD。

        Args:
            features: 含 momentum / volume / trend 的特征字典。

        Returns:
            交易信号。
        """
        score = 0
        if features["momentum"] > 0:
            score += 40
        if features["volume"] > 1.5:
            score += 30
        if features["trend"] == "UP":
            score += 30
        if score >= 70:
            return "BUY"
        elif score <= 30:
            return "SELL"
        return "HOLD"
