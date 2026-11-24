"""V2.5 VaR 风险模型：当前组合在一定概率下最大可能损失。"""
import numpy as np


class VaRModel:
    """Value at Risk：排序历史收益取分位。"""

    def calculate(self, returns, confidence=0.95):
        losses = np.sort(returns)
        index = int(len(losses) * (1 - confidence))
        return losses[index]
