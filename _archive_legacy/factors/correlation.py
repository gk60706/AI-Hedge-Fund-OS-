"""V3.2 相关性工具：计算两个序列的相关系数。"""

from __future__ import annotations

import numpy as np


def calculate_correlation(a, b) -> float:
    """计算两个收益序列的 Pearson 相关系数。

    Args:
        a: 序列 1（list / np.ndarray）。
        b: 序列 2（list / np.ndarray）。

    Returns:
        相关系数（-1 到 1）。
    """
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if len(x) != len(y):
        raise ValueError("两个序列长度必须一致")
    if len(x) < 2:
        return 0.0
    if np.std(x, ddof=1) < 1e-12 or np.std(y, ddof=1) < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])
