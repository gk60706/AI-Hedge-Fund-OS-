"""动量因子 (V0.5)

20 日动量因子：衡量股票价格在最近 period 个交易日内的涨跌幅。
"""
import pandas as pd


def momentum_factor(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """计算 20 日动量因子。

    :param df: 包含 ``close`` 列的行情 DataFrame
    :param period: 动量回看周期（默认 20 日）
    :return: 追加 ``momentum`` 列后的 DataFrame
    """
    df["momentum"] = (df["close"] / df["close"].shift(period) - 1)
    return df



# ============================================================================
# V3.8 AI Alpha Research Engine - momentum factor classes
# ============================================================================
from factors.base import Factor


class MomentumFactor(Factor):
    name = "momentum_20"

    def __init__(
        self,
        period: int = 20,
    ):
        self.period = period

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        close = pd.to_numeric(data["close"], errors="coerce",)
        return (close / close.shift(self.period) - 1.0)


class Momentum60Factor(Factor):
    name = "momentum_60"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        close = pd.to_numeric(data["close"], errors="coerce",)
        return (close / close.shift(60) - 1.0)


class Momentum120Factor(Factor):
    name = "momentum_120"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        close = pd.to_numeric(data["close"], errors="coerce",)
        return (close / close.shift(120) - 1.0)
