"""V3.2 Beta 控制：限制组合整体 Beta。"""

from __future__ import annotations


class BetaController:
    """组合 Beta 控制器。

    示例：目标 Beta = 0.85，最大 Beta = 1.10。
    组合 Beta 超过上限时按目标 Beta 等比缩仓。
    """

    def __init__(
        self,
        target_beta: float = 0.85,
        max_beta: float = 1.10,
    ):
        self.target_beta = target_beta
        self.max_beta = max_beta

    def adjust(
        self,
        weights: dict[str, float],
        betas: dict[str, float],
    ) -> dict[str, float]:
        """根据个股 Beta 调整组合权重。

        Args:
            weights: {code: weight}。
            betas: {code: beta}。

        Returns:
            调整后的 {code: weight}。
        """
        if not weights:
            return {}
        portfolio_beta = sum(
            weights.get(code, 0.0) * betas.get(code, 1.0)
            for code in weights
        )
        if portfolio_beta <= self.max_beta:
            return weights
        scale = self.target_beta / max(portfolio_beta, 1e-6)
        return {
            code: weight * scale
            for code, weight in weights.items()
        }
