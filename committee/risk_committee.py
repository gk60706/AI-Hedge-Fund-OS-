"""V1.0 风险委员会：评估组合整体风险并给出处置建议。"""


class RiskCommittee:
    def check(self, portfolio):
        risk = 0
        for stock in portfolio:
            risk += stock.get("volatility", 0.2)
        risk /= len(portfolio)
        if risk > 0.3:
            return {"status": "RED", "action": "REDUCE"}
        return {"status": "NORMAL", "action": "HOLD"}
