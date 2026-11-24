"""收益率计算 (V3.3)

基于历史价格序列计算对数/简单收益率。
"""
from __future__ import annotations

import pandas as pd


def calculate_returns(
    price_df: pd.DataFrame,
    price_column: str = "close",
) -> pd.Series:
    """计算价格序列的简单收益率（pct_change），剔除首日 NaN。

    :param price_df: 含价格列的 DataFrame。
    :param price_column: 价格列名，默认 close。
    :return: 收益率 Series（索引与 price_df 对齐，去掉首行）。
    """
    if price_column not in price_df.columns:
        raise ValueError(f"缺少价格字段:{price_column}")
    prices = price_df[price_column].astype(float)
    return prices.pct_change().dropna()
