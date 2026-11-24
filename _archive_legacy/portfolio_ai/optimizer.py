"""V2.6 Markowitz 组合优化（简化版）：等权组合。"""
import numpy as np


class PortfolioOptimizer:
    """组合优化器。"""

    def optimize(self, stocks):
        count = len(stocks)
        weight = np.ones(count) / count
        portfolio = {}
        for i, stock in enumerate(stocks):
            portfolio[stock] = round(float(weight[i]), 3)
        return portfolio
