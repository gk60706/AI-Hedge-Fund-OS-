"""V2.6 Black-Litterman 模型：市场默认权重 + AI 观点。"""


class BlackLitterman:
    """Black-Litterman 权重调整。"""

    def adjust(self, market_weight, ai_view):
        result = {}
        for stock in market_weight:
            result[stock] = (
                market_weight[stock]
                + ai_view.get(stock, 0)
            )
        return result
