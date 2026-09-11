"""V1.9 AI 策略生成器：随机生成第一代策略 DNA。"""

import random

from strategy.strategy_template import StrategyDNA


class StrategyGenerator:
    """在合法参数区间内随机生成策略 DNA。"""

    def generate(self) -> StrategyDNA:
        """生成一条随机策略 DNA。"""
        return StrategyDNA(
            ma_fast=random.randint(3, 20),
            ma_slow=random.randint(20, 120),
            rsi_buy=random.randint(20, 40),
            rsi_sell=random.randint(60, 90),
            volume_factor=random.uniform(1.2, 3),
            stop_loss=random.uniform(0.03, 0.1),
            take_profit=random.uniform(0.05, 0.3),
        )
