"""V3.2 风险状态：定义整个基金当前处于什么风险状态。"""

from __future__ import annotations

from enum import Enum


class RiskState(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    DEFENSIVE = "DEFENSIVE"
    EMERGENCY = "EMERGENCY"


class RiskStateEngine:
    """根据最大回撤与组合波动率评估当前风险状态。"""

    def evaluate(
        self,
        max_drawdown: float,
        portfolio_volatility: float,
    ) -> RiskState:
        """评估风险状态。

        Args:
            max_drawdown: 最大回撤（负数）。
            portfolio_volatility: 组合年化波动率。

        Returns:
            RiskState 枚举。
        """
        if (max_drawdown <= -0.20 or portfolio_volatility >= 0.40):
            return RiskState.EMERGENCY
        if (max_drawdown <= -0.15 or portfolio_volatility >= 0.30):
            return RiskState.DEFENSIVE
        if (max_drawdown <= -0.08 or portfolio_volatility >= 0.22):
            return RiskState.WARNING
        return RiskState.NORMAL
