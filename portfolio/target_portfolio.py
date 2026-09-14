"""目标仓位 (V3.3)

目标权重 vs 当前权重的差值描述。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TargetPosition:
    """单只股票的目标仓位。

    :param code: 股票代码。
    :param target_weight: 目标权重（0-1）。
    :param current_weight: 当前权重（0-1），默认 0。
    """

    code: str
    target_weight: float
    current_weight: float = 0.0

    @property
    def delta(self) -> float:
        """目标与当前权重的差值（>0 需买入，<0 需卖出）。"""
        return self.target_weight - self.current_weight
