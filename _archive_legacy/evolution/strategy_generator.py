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


class StrategyGeneratorV28:
    """V2.8 框架演示版：随机生成策略基因 dict（价值/动量/资金/持仓）。"""

    def generate(self):
        genes = {
            "value": random.random(),
            "momentum": random.random(),
            "capital": random.random(),
            "holding": random.randint(5, 60),
        }
        return genes


class StrategyGeneratorV281:
    """V2.8.1 可运行版：随机生成 StrategyV281 对象（9 基因位合法区间）。"""

    def generate(self):
        from strategy_lab.strategy import StrategyV281, StrategyDNA
        dna = StrategyDNA(
            momentum_weight=random.random(),
            value_weight=random.random(),
            capital_weight=random.random(),
            volume_weight=random.random(),
            buy_threshold=random.uniform(0.50, 0.90),
            stop_loss=random.uniform(0.03, 0.10),
            take_profit=random.uniform(0.08, 0.30),
            holding_period=random.randint(5, 40),
            max_position=random.uniform(0.05, 0.25),
        )
        return StrategyV281(dna)

    def generate_population(self, size=100):
        return [self.generate() for _ in range(size)]
