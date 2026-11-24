"""V1.3 趋势交易 Agent：动量 + 量能放大打分。"""

from agents.base_manager import InvestmentManager


class TrendAgent(InvestmentManager):
    """趋势交易经理：正向动量 + 成交量放大加分。"""

    def analyze(self, stock: dict) -> dict:
        score = 50
        if stock.get("momentum", 0) > 0:
            score += 30
        if stock.get("volume", 0) > 1.5:
            score += 20
        return {
            "manager": self.name,
            "style": "TREND",
            "score": score,
        }

# ============================================================
# V2.9 AI 多 Agent 投资委员会
# ============================================================

from typing import Any

from agents.base_agent import BaseAgent

class TrendAgentV29(BaseAgent):
    name = "trend_agent"

    def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        data = context.get("market_data", {})
        change_pct = data.get("change_pct")
        score = 50.0
        reasons = []
        if change_pct is not None:
            if change_pct >= 3:
                score += 20
                reasons.append("短线价格动能较强")
            elif change_pct >= 1:
                score += 10
                reasons.append("价格处于偏强状态")
            elif change_pct <= -3:
                score -= 20
                reasons.append("短线下跌压力明显")
            elif change_pct <= -1:
                score -= 10
                reasons.append("短线偏弱")
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
