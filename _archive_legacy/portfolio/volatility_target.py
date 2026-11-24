"""V3.2 波动率目标：按目标波动率自动缩放仓位暴露。"""

from __future__ import annotations


class VolatilityTarget:
    """波动率目标管理器。

    假设组合目标年化波动率 15%，当前组合波动率 25%，
    则系统自动降低仓位（exposure = target / current）。
    """

    def __init__(
        self,
        target_volatility: float = 0.15,
        min_exposure: float = 0.20,
        max_exposure: float = 0.95,
    ):
        self.target_volatility = target_volatility
        self.min_exposure = min_exposure
        self.max_exposure = max_exposure

    def calculate_exposure(self, portfolio_volatility: float) -> float:
        """根据当前组合波动率计算目标仓位暴露。

        Args:
            portfolio_volatility: 当前组合年化波动率。

        Returns:
            暴露比例（min_exposure ~ max_exposure）。
        """
        if portfolio_volatility <= 0:
            return self.max_exposure
        exposure = self.target_volatility / portfolio_volatility
        return max(
            self.min_exposure,
            min(self.max_exposure, exposure),
        )
