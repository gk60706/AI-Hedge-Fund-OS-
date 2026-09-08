"""虚拟资金账户 (V0.7)

模拟基金账户：现金 + 持仓市值 = 总资产。
"""


class Account:
    """虚拟资金账户。"""

    def __init__(self, cash: float = 1000000):
        self.cash = cash
        self.total_asset = cash
        self.positions = {}

    def update_asset(self, market: dict) -> None:
        """按最新行情更新总资产。"""
        value = self.cash
        for code, pos in self.positions.items():
            price = market.get(code, 0)
            value += price * pos["volume"]
        self.total_asset = value

    def get_balance(self) -> dict:
        """账户余额快照。"""
        return {
            "cash": self.cash,
            "asset": self.total_asset,
            "positions": self.positions,
        }
