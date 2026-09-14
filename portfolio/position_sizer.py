"""仓位换算 (V3.3/V3.4)

A 股以 100 股为一手，目标权重需换算为整数手股数。
"""
from __future__ import annotations


class PositionSizer:
    """将目标权重换算为 A 股整数手股数。

    V3.3 提供 shares_from_weight（返回股数）；
    V3.4 升级为 calculate（返回股数/市值/实际权重）。
    """

    def __init__(self, lot_size: int = 100):
        self.lot_size = lot_size

    def shares_from_weight(
        self,
        total_equity: float,
        target_weight: float,
        price: float,
    ) -> int:
        """按目标权重换算整数手股数（向下取整到 100 股）。

        :param total_equity: 总资产。
        :param target_weight: 目标权重（0-1）。
        :param price: 当前价格。
        :return: 股数（100 的整数倍）。
        """
        if price <= 0:
            return 0
        target_value = total_equity * target_weight
        raw_shares = target_value / price
        shares = int(raw_shares / self.lot_size) * self.lot_size
        return max(shares, 0)

    def calculate(
        self,
        total_equity: float,
        target_weight: float,
        price: float,
    ) -> dict:
        """V3.4 升级版仓位换算。

        :return: {"shares", "value", "actual_weight"}。
        """
        if total_equity <= 0 or price <= 0:
            return {
                "shares": 0,
                "value": 0.0,
                "actual_weight": 0.0,
            }
        target_value = total_equity * target_weight
        shares = int(target_value / price / self.lot_size) * self.lot_size
        value = shares * price
        actual_weight = value / total_equity
        return {
            "shares": shares,
            "value": value,
            "actual_weight": actual_weight,
        }
