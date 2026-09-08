"""股票组合优化 (V0.6)

简化版 Markowitz 最优化：基于收益协方差矩阵求最小方差组合权重。
"""
import numpy as np


def markowitz_optimizer(returns) -> list:
    """简化版 Markowitz 组合优化。

    :param returns: 收益矩阵（每行一只股票的时间序列收益）
    :return: 组合权重列表（和为 1）
    """
    cov = np.cov(returns)
    inv = np.linalg.inv(cov)
    weights = inv.sum(axis=1)
    weights = weights / weights.sum()
    return weights.tolist()
