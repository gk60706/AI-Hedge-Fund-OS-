"""组合目标函数 (V3.4)

Objective = ER - risk_aversion×Vol - turnover_penalty×Turnover - Cost
"""
from __future__ import annotations


class PortfolioObjective:
    """组合优化目标函数。"""

    def calculate(
        self,
        expected_return: float,
        volatility: float,
        turnover: float,
        transaction_cost: float,
        risk_aversion: float = 2.0,
        turnover_penalty: float = 0.5,
    ) -> float:
        """计算目标函数值（越大越好）。

        :param expected_return: 组合预期收益。
        :param volatility: 组合波动率。
        :param turnover: 换手率。
        :param transaction_cost: 交易成本。
        :param risk_aversion: 风险厌恶系数。
        :param turnover_penalty: 换手惩罚系数。
        :return: 目标值。
        """
        return (
            expected_return
            - risk_aversion * volatility
            - turnover_penalty * turnover
            - transaction_cost
        )
