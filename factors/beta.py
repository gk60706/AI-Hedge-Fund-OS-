"""V3.2 个股 Beta 计算：Beta = Cov(stock, benchmark) / Var(benchmark)。"""

from __future__ import annotations

import numpy as np


def calculate_beta(
    stock_returns,
    benchmark_returns,
) -> float:
    """计算个股相对基准的 Beta。

    Beta = Cov(stock, benchmark) / Var(benchmark)

    Args:
        stock_returns: 个股收益序列。
        benchmark_returns: 基准收益序列。

    Returns:
        Beta 值。数据不足或基准方差为零时返回 1.0。
    """
    stock = np.asarray(stock_returns, dtype=float)
    benchmark = np.asarray(benchmark_returns, dtype=float)
    if len(stock) != len(benchmark):
        raise ValueError("股票收益率与基准收益率长度必须一致")
    if len(stock) < 2:
        return 1.0
    benchmark_var = np.var(benchmark)
    if benchmark_var <= 1e-12:
        return 1.0
    covariance = np.cov(stock, benchmark, ddof=1)[0, 1]
    return float(covariance / benchmark_var)
