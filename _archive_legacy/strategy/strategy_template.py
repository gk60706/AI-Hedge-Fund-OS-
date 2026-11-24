"""V1.9 策略 DNA 定义（Strategy DNA）。

AI 不能凭空创造策略——先用 dataclass 定义可进化、可变异、可交叉的
策略基因结构。研究/模拟用途，不连接任何实盘交易接口。
"""

from dataclasses import dataclass


@dataclass
class StrategyDNA:
    """策略基因：技术指标参数组合。"""

    # 技术指标
    ma_fast: int
    ma_slow: int
    rsi_buy: int
    rsi_sell: int
    volume_factor: float
    stop_loss: float
    take_profit: float

    def mutation(self) -> "StrategyDNA":
        """随机变异部分基因参数，返回自身。"""
        import random

        self.ma_fast += random.randint(-2, 2)
        self.rsi_buy += random.randint(-5, 5)
        self.volume_factor *= random.uniform(0.9, 1.1)
        return self
