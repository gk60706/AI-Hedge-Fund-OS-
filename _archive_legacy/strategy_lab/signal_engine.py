"""V2.8.1 策略信号生成器：按策略 DNA 加权特征得分产生买卖信号。"""
import numpy as np


class StrategySignalEngine:
    """策略信号引擎。"""

    def generate(self, strategy, features):
        dna = strategy.dna
        scores = (
            features["momentum"] * dna.momentum_weight
            + features["value"] * dna.value_weight
            + features["capital"] * dna.capital_weight
            + features["volume"] * dna.volume_weight
        )
        signals = np.zeros(len(scores), dtype=int)
        signals[scores >= dna.buy_threshold] = 1
        signals[scores <= 0.25] = -1
        return signals
