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
