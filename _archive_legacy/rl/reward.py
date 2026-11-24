"""V1.7 奖励引擎：收益 - 回撤惩罚 - 过度交易惩罚。"""


class RewardEngine:
    """奖励函数：好策略 = 收益↑ + 回撤↓ + 交易次数↓。"""

    def calculate(self, portfolio_return: float, drawdown: float, turnover: float) -> float:
        reward = portfolio_return
        # 惩罚回撤
        reward -= 0.5 * max(drawdown, 0)
        # 惩罚过度交易
        reward -= 0.01 * turnover
        return reward
