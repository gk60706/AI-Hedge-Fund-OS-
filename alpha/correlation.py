from __future__ import annotations

import pandas as pd


class FactorCorrelation:
    def calculate(
        self,
        factors: pd.DataFrame,
    ) -> pd.DataFrame:
        return factors.corr(method="spearman")
# ============================================================================
# V3.9.1 unified research engine - pairwise signal correlation (scalar)
# ============================================================================


def signal_correlation(a: pd.Series, b: pd.Series) -> float:
    temp = pd.concat([a, b], axis=1).dropna()
    if len(temp) < 10:
        return float("nan")
    return float(temp.iloc[:, 0].corr(temp.iloc[:, 1], method="spearman"))
