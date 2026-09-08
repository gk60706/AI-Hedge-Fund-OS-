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
