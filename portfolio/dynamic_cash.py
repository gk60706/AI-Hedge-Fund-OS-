"""V3.2 动态现金：市场越危险，自动持有现金越多。"""

from __future__ import annotations


class DynamicCashManager:
    """动态现金管理器。

    高波动 / 深回撤 / 弱市场时自动提高现金比例。
    """

    def calculate_cash_ratio(
        self,
        portfolio_volatility: float,
        max_drawdown: float,
        market_score: float,
    ) -> float:
        """计算目标现金比例。

        Args:
            portfolio_volatility: 组合年化波动率。
            max_drawdown: 最大回撤（负数）。
            market_score: 市场评分（0-100）。

        Returns:
            现金比例（上限 60%）。
        """
        cash = 0.05
        # 高波动
        if portfolio_volatility >= 0.25:
            cash += 0.10
        if portfolio_volatility >= 0.35:
            cash += 0.10
        # 回撤
        if max_drawdown <= -0.10:
            cash += 0.10
        if max_drawdown <= -0.15:
            cash += 0.10
        if max_drawdown <= -0.20:
            cash += 0.15
        # 市场评分
        if market_score < 40:
            cash += 0.10
        if market_score < 30:
            cash += 0.10
        return min(cash, 0.60)
