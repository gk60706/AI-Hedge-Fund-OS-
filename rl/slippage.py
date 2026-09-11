"""V1.8 滑点模型：模拟成交价偏移。"""


class SlippageModel:
    """简化滑点模型：成交价按 0.05% 上浮（买入侧）。"""

    def apply(self, price: float, volume: float) -> float:
        """按价格与成交量计算含滑点成交价。

        Args:
            price: 基准价格。
            volume: 成交量（保留参数，便于后续扩展）。

        Returns:
            滑点调整后价格。
        """
        slip = 0.0005
        return price * (1 + slip)
