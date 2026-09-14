"""Ensemble 组合优化器 (V3.4)

融合 Mean-Variance / Risk Parity / Black-Litterman / Alpha 四路信号。
"""
from __future__ import annotations

from typing import Any


class EnsembleOptimizer:
    """多模型权重融合。"""

    def combine(
        self,
        mean_variance: dict[str, float],
        risk_parity: dict[str, float],
        black_litterman: dict[str, float],
        alpha_scores: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """融合四路信号为最终权重。

        :param mean_variance: MV 权重。
        :param risk_parity: RP 权重。
        :param black_litterman: BL 权重。
        :param alpha_scores: Alpha 分数（0-100）。
        :param weights: 融合权重，默认 mv=0.30/rp=0.30/bl=0.20/alpha=0.20。
        :return: 归一化后的融合权重。
        """
        if weights is None:
            weights = {
                "mv": 0.30,
                "rp": 0.30,
                "bl": 0.20,
                "alpha": 0.20,
            }

        codes = (
            set(mean_variance)
            | set(risk_parity)
            | set(black_litterman)
            | set(alpha_scores)
        )
        result = {}
        for code in codes:
            mv = mean_variance.get(code, 0.0)
            rp = risk_parity.get(code, 0.0)
            bl = black_litterman.get(code, 0.0)
            alpha = alpha_scores.get(code, 50.0) / 100.0
            result[code] = (
                weights["mv"] * mv
                + weights["rp"] * rp
                + weights["bl"] * bl
                + weights["alpha"] * alpha
            )

        total = sum(result.values())
        if total > 0:
            result = {
                code: value / total
                for code, value in result.items()
            }
        return result
