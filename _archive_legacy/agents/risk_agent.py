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

# ============================================================
# V2.9 AI 多 Agent 投资委员会
# ============================================================

from typing import Any

from agents.base_agent import BaseAgent

class RiskAgentV29(BaseAgent):
    name = "risk_agent"

    def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        data = context.get("risk", {})
        max_drawdown = float(data.get("max_drawdown", 0))
        volatility = float(data.get("volatility", 0))
        score = 100.0
        reasons = []
        if max_drawdown < -0.30:
            score -= 40
            reasons.append("历史最大回撤过高")
        elif max_drawdown < -0.20:
            score -= 25
            reasons.append("历史最大回撤较高")
        elif max_drawdown < -0.10:
            score -= 10
            reasons.append("存在中等回撤风险")
        if volatility > 0.05:
            score -= 20
            reasons.append("波动率较高")
        score = self.normalize_score(score)
        if score >= 70:
            signal = "LOW_RISK"
        elif score >= 45:
            signal = "MEDIUM_RISK"
        else:
            signal = "HIGH_RISK"
        return {
            "agent": self.name,
            "score": score,
            "signal": signal,
            "reasons": reasons,
        }
