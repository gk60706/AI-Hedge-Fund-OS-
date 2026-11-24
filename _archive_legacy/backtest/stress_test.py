"""V3.5 StressTestEngine：压力测试。

主动制造极端行情：
- crash_20 / crash_30：中段一次性下跌 20% / 30%
- high_volatility：高波动冲击
"""

from __future__ import annotations

import numpy as np


class StressTestEngine:
    def apply_crash(self, prices, crash=-0.20):
        prices = np.asarray(prices, dtype=float).copy()
        if len(prices) == 0:
            return prices
        crash_index = len(prices) // 2
        prices[crash_index:] *= 1 + crash
        return prices

    def apply_high_volatility(self, prices, volatility=0.05, seed=42):
        rng = np.random.default_rng(seed)
        prices = np.asarray(prices, dtype=float).copy()
        if len(prices) == 0:
            return prices
        shocks = rng.normal(0, volatility, len(prices))
        prices = prices * np.cumprod(1 + shocks)
        return prices

    def run(self, prices):
        return {
            "crash_20": self.apply_crash(prices, -0.20),
            "crash_30": self.apply_crash(prices, -0.30),
            "high_volatility": self.apply_high_volatility(prices),
        }
