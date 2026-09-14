"""Mean-Variance 优化器 (V3.4)

权重正比于 inv(Σ)·μ，负权重清零，单票上限 max_weight。
"""
from __future__ import annotations

import numpy as np


class MeanVarianceOptimizer:
    """基于均值-方差框架的权重求解。"""

    def __init__(
        self,
        risk_aversion: float = 2.0,
        max_weight: float = 0.20,
    ):
        self.risk_aversion = risk_aversion
        self.max_weight = max_weight

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance: np.ndarray,
        codes: list[str],
    ) -> dict[str, float]:
        """求解组合权重。

        :param expected_returns: 代码 -> 预期收益。
        :param covariance: 协方差矩阵。
        :param codes: 股票代码列表（与矩阵行列对应）。
        :return: 代码 -> 权重。
        """
        n = len(codes)
        if n == 0:
            return {}

        mu = np.array(
            [expected_returns.get(code, 0.0) for code in codes],
            dtype=float,
        )
        covariance = np.asarray(covariance, dtype=float)
        # 对称化 + 抖动，保证可逆
        covariance = (covariance + covariance.T) / 2
        covariance = covariance + np.eye(n) * 1e-8

        try:
            inv_cov = np.linalg.pinv(covariance)
            raw = inv_cov @ mu
        except np.linalg.LinAlgError:
            raw = np.ones(n)

        raw = np.maximum(raw, 0.0)
        if raw.sum() <= 0:
            raw = np.ones(n)

        weights = raw / raw.sum()
        # 单票上限
        weights = np.minimum(weights, self.max_weight)
        total = weights.sum()
        if total > 0:
            weights = weights / total

        return {
            code: float(weight)
            for code, weight in zip(codes, weights)
        }
