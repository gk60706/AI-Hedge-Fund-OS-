"""V2.5 AI 风险委员会投票。"""


class RiskCommittee:
    """风险委员会：多 Agent 投票（>=2 票拒绝则拒绝）。"""

    def vote(self, opinions):
        reject = opinions.count("REJECT")
        approve = opinions.count("APPROVE")
        if reject >= 2:
            return "REJECT"
        return "APPROVE"
