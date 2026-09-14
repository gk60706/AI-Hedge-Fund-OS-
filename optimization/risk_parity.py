"""Risk Parity 优化器 (V3.4)

权重与波动率成反比（1/σ），归一化后施加单票上限。
"""
from __future__ import annotations

import numpy as np


class RiskParityOptimizer:
    """简化风险平价：w_i ∝ 1/σ_i。"""

    def optimize(
        self,
        covariance: np.ndarray,
        codes: list[str],
        max_weight: float = 0.20,
    ) -> dict[str, float]:
        """求解风险平价权重。

        :param covariance: 协方差矩阵。
        :param codes: 股票代码列表。
        :param max_weight: 单票权重上限。
        :return: 代码 -> 权重。
        """
        n = len(codes)
        if n == 0:
            return {}

        covariance = np.asarray(covariance, dtype=float)
        volatility = np.sqrt(
            np.maximum(np.diag(covariance), 1e-8),
        )
        inverse_vol = 1.0 / volatility
        weights = inverse_vol / inverse_vol.sum()

        weights = np.minimum(weights, max_weight)
        if weights.sum() > 0:
            weights = weights / weights.sum()

        return {
            code: float(weight)
            for code, weight in zip(codes, weights)
        }
