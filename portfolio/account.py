"""V2.4 资金账户系统。"""


class Account:
    """模拟资金账户。"""

    def __init__(self, cash=1000000):
        self.cash = cash
        self.positions = {}

    def value(self, prices):
        """按市价计算账户总资产。"""
        total = self.cash
        for code, qty in self.positions.items():
            total += (qty * prices[code])
        return total
