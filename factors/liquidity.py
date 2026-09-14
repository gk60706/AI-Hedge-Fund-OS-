from __future__ import annotations

import pandas as pd

from factors.base import Factor


class TurnoverFactor(Factor):
    name = "turnover"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        return pd.to_numeric(data["turnover"], errors="coerce",)


class Amount20Factor(Factor):
    name = "amount_20"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        amount = pd.to_numeric(data["amount"], errors="coerce",)
        return (amount.rolling(20).mean())
