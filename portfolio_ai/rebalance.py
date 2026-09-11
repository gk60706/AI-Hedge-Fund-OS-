"""V2.6 动态调仓系统：目标权重与当前权重偏差 >5% 时生成调仓订单。"""


class RebalanceEngine:
    """动态调仓引擎。"""

    def rebalance(self, current, target):
        orders = []
        for stock in target:
            diff = (
                target[stock]
                - current.get(stock, 0)
            )
            if abs(diff) > 0.05:
                orders.append(
                    {
                        "stock": stock,
                        "change": diff,
                    }
                )
        return orders
