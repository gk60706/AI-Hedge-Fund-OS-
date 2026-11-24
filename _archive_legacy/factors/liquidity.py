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


# ============================================================================
# V3.9.1 unified research engine - composite liquidity factor
# ============================================================================


class LiquidityFactor:
    def __init__(self, turnover: bool = True, amount: bool = True):
        self.include_turnover = turnover
        self.include_amount = amount

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.0, index=data.index)
        count = pd.Series(0, index=data.index)
        if self.include_turnover and "turnover" in data:
            score = score + data["turnover"].fillna(0.0)
            count = count + data["turnover"].notna().astype(int)
        if self.include_amount and "amount_20" in data:
            score = score + data["amount_20"].fillna(0.0)
            count = count + data["amount_20"].notna().astype(int)
        return score / count.replace(0, 1)
