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
