"""V2.5 组合风险预算：等权分散，避免单票重仓。"""


class RiskBudget:
    """按股票数等权分配风险预算。"""

    def allocate(self, stocks):
        result = {}
        weight = 1 / len(stocks)
        for stock in stocks:
            result[stock] = weight
        return result
