from __future__ import annotations

import pandas as pd


class FactorCorrelation:
    def calculate(
        self,
        factors: pd.DataFrame,
    ) -> pd.DataFrame:
        return factors.corr(method="spearman")
