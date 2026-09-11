"""V2.4 持仓管理。"""


class PositionManager:
    """持仓统计。"""

    def check(self, account):
        return {
            "stocks": len(account.positions),
            "positions": account.positions,
        }
