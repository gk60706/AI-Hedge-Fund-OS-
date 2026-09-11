"""V2.6 组合管理器：持仓权重总览。"""


class PortfolioManager:
    """组合管理器。"""

    def __init__(self):
        self.positions = {}

    def add_position(self, code, weight):
        self.positions[code] = weight

    def total_weight(self):
        return sum(self.positions.values())

    def check(self):
        return {
            "positions": self.positions,
            "total": self.total_weight(),
        }
