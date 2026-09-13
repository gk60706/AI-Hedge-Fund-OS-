"""V3.2 波动率工具：计算收益序列的年化波动率。"""

from __future__ import annotations

import numpy as np


def calculate_volatility(returns, annualize: int = 252) -> float:
    """计算收益序列的年化波动率。

    Args:
        returns: 收益序列（list / np.ndarray）。
        annualize: 年化系数（默认 252 个交易日）。

    Returns:
        年化波动率（0-1 区间的小数）。
    """
    arr = np.asarray(returns, dtype=float)
    if len(arr) < 2:
        return 0.0
    return float(np.std(arr, ddof=1) * np.sqrt(annualize))
