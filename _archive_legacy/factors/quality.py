from __future__ import annotations

import pandas as pd

from factors.base import Factor


class ROEFactor(Factor):
    name = "roe"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        return pd.to_numeric(data["roe"], errors="coerce",)


class ROICFactor(Factor):
    name = "roic"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        return pd.to_numeric(data["roic"], errors="coerce",)


class RevenueGrowthFactor(Factor):
    name = "revenue_growth"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        return pd.to_numeric(data["revenue_growth"], errors="coerce",)


class ProfitGrowthFactor(Factor):
    name = "profit_growth"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        return pd.to_numeric(data["profit_growth"], errors="coerce",)


# ============================================================================
# V3.9.1 unified research engine - composite quality factor
# ============================================================================


class QualityFactor:
    def __init__(
        self,
        roe: bool = True,
        roic: bool = True,
        revenue_growth: bool = True,
        profit_growth: bool = True,
    ):
        self.include_roe = roe
        self.include_roic = roic
        self.include_revenue_growth = revenue_growth
        self.include_profit_growth = profit_growth

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.0, index=data.index)
        count = pd.Series(0, index=data.index)
        for flag, col in [
            (self.include_roe, "roe"),
            (self.include_roic, "roic"),
            (self.include_revenue_growth, "revenue_growth"),
            (self.include_profit_growth, "profit_growth"),
        ]:
            if flag and col in data:
                score = score + data[col].fillna(0.0)
                count = count + data[col].notna().astype(int)
        return score / count.replace(0, 1)
