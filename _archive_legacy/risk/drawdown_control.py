"""V3.2 回撤控制：按最大回撤计算仓位系数。"""

from __future__ import annotations


class DrawdownController:
    """回撤控制引擎。

    最大回撤 → 仓位系数：
        > -8%   → 100%
        -8~-12% → 85%
        -12~-15% → 70%
        -15~-20% → 50%
        -20~-25% → 30%
        < -25%  → 15%
    """

    def calculate_exposure_multiplier(self, max_drawdown: float) -> float:
        """根据最大回撤计算仓位暴露系数。

        Args:
            max_drawdown: 最大回撤（负数）。

        Returns:
            仓位系数（0.15 ~ 1.00）。
        """
        if max_drawdown > -0.08:
            return 1.00
        if max_drawdown > -0.12:
            return 0.85
        if max_drawdown > -0.15:
            return 0.70
        if max_drawdown > -0.20:
            return 0.50
        if max_drawdown > -0.25:
            return 0.30
        return 0.15
