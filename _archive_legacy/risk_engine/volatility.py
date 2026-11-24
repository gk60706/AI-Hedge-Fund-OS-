"""V2.5 波动率监控：年化波动率分级。"""
import numpy as np


class VolatilityMonitor:
    """波动率计算与风险等级。"""

    def calculate(self, returns):
        return np.std(returns) * np.sqrt(252)

    def level(self, volatility):
        if volatility > 0.4:
            return "HIGH"
        elif volatility > 0.25:
            return "MEDIUM"
        return "LOW"
