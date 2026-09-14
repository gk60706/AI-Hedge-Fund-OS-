"""V3.5 BenchmarkEngine：基准净值曲线（沪深300/中证1000/创业板指/上证指数接入点在真实数据版）。"""

from __future__ import annotations

import numpy as np


class BenchmarkEngine:
    """把基准价格序列转成 1,000,000 元起始的基准净值曲线。"""

    def calculate_equity(self, prices, initial_capital=1_000_000):
        prices = np.asarray(prices, dtype=float)
        if len(prices) == 0:
            return np.array([])
        returns = prices[1:] / prices[:-1] - 1
        equity = np.empty(len(prices))
        equity[0] = initial_capital
        equity[1:] = initial_capital * np.cumprod(1 + returns)
        return equity
