"""协方差矩阵引擎 (V3.3)

Covariance = Volatility × Correlation × Volatility。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class CovarianceEngine:
    """基于收益率矩阵计算协方差矩阵与组合波动率。"""

    def calculate(
        self,
        returns: pd.DataFrame,
        annualize: bool = True,
    ) -> pd.DataFrame:
        """计算收益率矩阵的协方差矩阵。

        :param returns: 收益率矩阵（列 = 股票代码，行 = 交易日）。
        :param annualize: 是否年化（×252）。
        :return: 协方差矩阵 DataFrame。
        """
        covariance = returns.cov()
        if annualize:
            covariance = covariance * 252
        return covariance

    def portfolio_volatility(
        self,
        weights: dict[str, float],
        covariance: pd.DataFrame,
    ) -> float:
        """给定权重与协方差矩阵，计算组合年化波动率 = sqrt(w'Σw)。

        :param weights: 代码 -> 权重。
        :param covariance: 协方差矩阵 DataFrame。
        :return: 组合波动率。
        """
        codes = [code for code in weights if code in covariance.index]
        if not codes:
            return 0.0
        vector = np.array(
            [weights[code] for code in codes],
            dtype=float,
        )
        matrix = covariance.loc[codes, codes].values
        variance = vector @ matrix @ vector
        return float(np.sqrt(max(variance, 0.0)))
