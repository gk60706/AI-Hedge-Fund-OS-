"""V2.5 AI 风险委员会成员 Agent。"""


class RiskAgent:
    """风险 Agent：市场波动 + 单票仓位审核。"""

    def review(self, trade, market):
        if market["volatility"] > 0.5:
            return "REJECT"
        if trade["position"] > 0.3:
            return "REJECT"
        return "APPROVE"
