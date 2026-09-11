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


# ---------------------------------------------------------------------------
# V2.0 风控 Agent（多智能体基金经理系统）：最高权限，可否决交易。
# 与 V0.2 risk_agent 函数并存，不删除已有功能。
# ---------------------------------------------------------------------------
class RiskAgent:
    """V2.0 风控 Agent：单票仓位超限则否决。"""

    def check(self, stock: str, position: float) -> dict:
        """Args:
            stock: 股票代码。
            position: 拟建仓位比例。

        Returns:
            {"approved": bool, "reason": str}
        """
        if position > 0.3:
            return {"approved": False, "reason": "单票仓位过高"}
        return {"approved": True, "reason": "Risk OK"}
