"""回测指标 (V0.5)

最大回撤与夏普比率（基于 NumPy）。
"""
import numpy as np


def max_drawdown(values) -> float:
    """计算净值序列的最大回撤（0-1，越大回撤越深）。

    :param values: 净值序列（iterable of float）
    """
    peak = values[0]
    max_dd = 0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return max_dd


def sharpe(returns) -> float:
    """计算收益序列的夏普比率（简化版，无风险利率取 0）。

    :param returns: 收益率序列（iterable of float）
    """
    return np.mean(returns) / np.std(returns)
