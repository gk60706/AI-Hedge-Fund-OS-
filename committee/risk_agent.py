"""V1.3 风险委员会 Agent：评估组合平均风险并给出动作。"""


class RiskAgent:
    """风险委员会：组合平均风险 > 0.3 时要求减仓，否则维持。"""

    def check(self, portfolio: list) -> dict:
        total_risk = 0
        for stock in portfolio:
            total_risk += stock.get("risk", 0.1)
        avg_risk = total_risk / len(portfolio)
        if avg_risk > 0.3:
            return {
                "status": "HIGH",
                "action": "REDUCE",
            }
        return {
            "status": "NORMAL",
            "action": "KEEP",
        }
