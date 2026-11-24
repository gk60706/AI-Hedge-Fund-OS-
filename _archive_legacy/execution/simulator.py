"""V2.4 模拟交易执行器。"""


class SimulatorBroker:
    """模拟成交（Simulator → 未来 QMT → 真实券商 API）。"""

    def __init__(self, account):
        self.account = account

    def send_order(self, order):
        """模拟撮合：BUY 扣现金加持仓，SELL 减持仓。"""
        if order.side == "BUY":
            cost = (order.price * order.quantity)
            self.account.cash -= cost
            self.account.positions[order.code] = (
                self.account.positions.get(order.code, 0) + order.quantity
            )
        elif order.side == "SELL":
            self.account.positions[order.code] -= order.quantity
        return {"status": "FILLED", "order": order}
