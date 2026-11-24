"""V2.4 持仓管理。"""


class PositionManager:
    """持仓统计。"""

    def check(self, account):
        return {
            "stocks": len(account.positions),
            "positions": account.positions,
        }

# ============================================================
# V3.0 AI Autonomous Hedge Fund：持仓数据结构
# ============================================================
from dataclasses import dataclass


@dataclass
class PositionV30:
    code: str
    name: str
    shares: int = 0
    avg_price: float = 0.0
    current_price: float = 0.0
    target_weight: float = 0.0
    stop_loss: float = 0.08
    take_profit: float = 0.20

    @property
    def market_value(self) -> float:
        return (
            self.shares
            * self.current_price
        )

    @property
    def pnl(self) -> float:
        return (
            self.current_price
            - self.avg_price
        ) * self.shares

    @property
    def pnl_pct(self) -> float:
        if self.avg_price <= 0:
            return 0.0
        return (
            self.current_price
            / self.avg_price
            - 1
        )
