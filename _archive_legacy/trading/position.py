"""持仓管理 (V0.7)

模拟持仓：买入累加成本与数量，卖出扣减数量。
"""


class Position:
    """持仓管理器。"""

    def __init__(self):
        self.positions = {}

    def buy(self, code: str, price: float, volume: int) -> None:
        """买入：累加持仓成本与数量。"""
        if code not in self.positions:
            self.positions[code] = {"volume": 0, "cost": 0}
        old = self.positions[code]
        total_cost = old["cost"] + price * volume
        total_volume = old["volume"] + volume
        old["volume"] = total_volume
        old["cost"] = total_cost

    def sell(self, code: str, volume: int) -> None:
        """卖出：扣减持仓数量。"""
        if code in self.positions:
            self.positions[code]["volume"] -= volume

    def get_positions(self) -> dict:
        return self.positions


class PositionManager:
    """V1.4 持仓管理：汇总券商现金与持仓视图。"""

    def summary(self, broker) -> dict:
        return {
            "cash": broker.cash,
            "positions": broker.positions,
        }

