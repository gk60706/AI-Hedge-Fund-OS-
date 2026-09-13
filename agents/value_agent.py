"""V1.3 价值投资 Agent：低 PE + 高 ROE 打分。"""

from agents.base_manager import InvestmentManager


class ValueAgent(InvestmentManager):
    """价值投资经理：偏好低估值（PE<30）与高盈利质量（ROE>15）。"""

    def analyze(self, stock: dict) -> dict:
        score = 50
        if stock.get("pe", 100) < 30:
            score += 20
        if stock.get("roe", 0) > 15:
            score += 20
        return {
            "manager": self.name,
            "style": "VALUE",
            "score": score,
        }

# ============================================================
# V2.9 AI 多 Agent 投资委员会
# ============================================================

from typing import Any

from agents.base_agent import BaseAgent

class ValueAgentV29(BaseAgent):
    name = "value_agent"

    def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        data = context.get("market_data", {})
        score = 50.0
        reasons = []
        pe = data.get("pe_dynamic")
        pb = data.get("pb")
        if pe is not None:
            if pe < 20:
                score += 15
                reasons.append("动态PE处于相对较低水平")
            elif pe > 60:
                score -= 15
                reasons.append("动态PE较高，估值压力较大")
        if pb is not None:
            if pb < 3:
                score += 10
                reasons.append("PB相对温和")
            elif pb > 8:
                score -= 10
                reasons.append("PB偏高")
        score = self.normalize_score(score)
        if score >= 70:
            signal = "BUY"
        elif score <= 40:
            signal = "SELL"
        else:
            signal = "HOLD"
        return {
            "agent": self.name,
            "score": score,
            "signal": signal,
            "reasons": reasons,
        }
