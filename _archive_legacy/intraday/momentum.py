"""V1.5 分钟动量因子：区间涨跌幅打分。"""


class MomentumAgent:
    """分钟动量因子 Agent。"""

    def score(self, prices: list) -> int:
        change = prices[-1] / prices[0] - 1
        if change > 0.03:
            return 90
        elif change > 0:
            return 70
        else:
            return 40
