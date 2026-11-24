"""V1.4 自动调仓系统：把股票池前 5 名补仓进模拟账户。"""


class RebalanceEngine:
    """自动调仓引擎（模拟，无实盘接口）。"""

    def rebalance(self, stocks: list, broker) -> dict:
        target = stocks[:5]
        for stock in target:
            if stock["code"] not in broker.positions:
                broker.buy(stock["code"], stock["price"], 100)
        return broker.positions
