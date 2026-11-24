"""V2.6 资金分配系统：A 级 20% / B 级 10% / 观察 5%。"""


class AssetAllocator:
    """按评分分配资金。"""

    def allocate(self, scores):
        allocation = {}
        for stock, score in scores.items():
            if score >= 90:
                allocation[stock] = 0.2
            elif score >= 80:
                allocation[stock] = 0.1
            else:
                allocation[stock] = 0.05
        return allocation
