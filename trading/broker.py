"""模拟券商 (V0.7)

模拟成交执行：BUY 买入 / SELL 卖出，记录订单流水。
"""
from trading.position import Position


class PaperBroker:
    """模拟券商（Paper Broker）。"""

    def __init__(self):
        self.position = Position()
        self.orders = []

    def execute(self, order) -> dict:
        """执行一笔模拟订单。"""
        if order.action == "BUY":
            self.position.buy(order.code, order.price, order.volume)
        elif order.action == "SELL":
            self.position.sell(order.code, order.volume)
        self.orders.append(order.to_dict())
        return {"status": "FILLED", "order": order.to_dict()}
