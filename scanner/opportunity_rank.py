"""V2.2 AI 机会排名系统：候选股按分数排名，取前 50。"""


class OpportunityRank:
    """AI 机会排名。"""

    def rank(self, stocks: list) -> list:
        """按 score 降序排名，返回前 50。"""
        return sorted(stocks, key=lambda x: x["score"], reverse=True)[:50]
