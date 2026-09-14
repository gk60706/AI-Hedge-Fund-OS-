"""Black-Litterman 模型 (V3.4)

先验均衡收益 = 风险厌恶 × Σ × 市值权重；
后验 = 均衡收益×(1-confidence) + 观点×confidence（简化实现）。
"""
from __future__ import annotations

import numpy as np


class BlackLittermanModel:
    """简化 Black-Litterman 后验收益估计。"""

    def __init__(self, tau: float = 0.05):
        self.tau = tau

    def calculate_posterior_returns(
        self,
        covariance: np.ndarray,
        market_weights: np.ndarray,
        views: np.ndarray,
        view_confidence: np.ndarray,
        risk_aversion: float = 2.5,
    ) -> np.ndarray:
        """计算后验预期收益。

        :param covariance: 协方差矩阵。
        :param market_weights: 市值权重。
        :param views: 主观观点（每只股票的预期收益）。
        :param view_confidence: 观点置信度（0-1）。
        :param risk_aversion: 风险厌恶系数。
        :return: 后验收益向量。
        """
        covariance = np.asarray(covariance, dtype=float)
        market_weights = np.asarray(market_weights, dtype=float)
        views = np.asarray(views, dtype=float)
        confidence = np.asarray(view_confidence, dtype=float)

        equilibrium_returns = risk_aversion * covariance @ market_weights
        if len(views) == 0:
            return equilibrium_returns

        confidence = np.clip(confidence, 0.0, 1.0)
        posterior = (
            equilibrium_returns * (1.0 - confidence)
            + views * confidence
        )
        return posterior
