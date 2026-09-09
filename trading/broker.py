"""模拟券商 (V0.7 + V1.4)

V0.7 接口：``execute(order)`` 按订单对象成交，持仓视图 ``self.position``。
V1.4 接口：``buy(code, price, amount)`` / ``sell(code)`` 直接成交，
          现金 ``self.cash`` 与持仓字典 ``self.positions``。
两套接口并存，均只做内存模拟，不接入任何真实交易通道。
"""
from trading.position import Position


class PaperBroker:
    """模拟券商（Paper Broker）。"""

    def __init__(self, capital: float = 1000000):
        self.position = Position()
        self.positions = {}
        self.cash = capital
        self.orders = []

    # ---- V0.7 接口 ----
    def execute(self, order) -> dict:
        """执行一笔模拟订单。"""
        if order.action == "BUY":
            self.position.buy(order.code, order.price, order.volume)
            self.buy(order.code, order.price, order.volume)
        elif order.action == "SELL":
            self.position.sell(order.code, order.volume)
            self.sell(order.code)
        self.orders.append(order.to_dict())
        return {"status": "FILLED", "order": order.to_dict()}

    # ---- V1.4 接口 ----
    def buy(self, code: str, price: float, amount: int) -> bool:
        """买入：现金充足则扣款并建仓。"""
        cost = price * amount
        if self.cash >= cost:
            self.cash -= cost
            self.positions[code] = {"price": price, "amount": amount}
            return True
        return False

    def sell(self, code: str) -> bool:
        """卖出：清仓指定股票。"""
        if code in self.positions:
            del self.positions[code]
            return True
        return False
