"""V3.9.1 backtest signal helpers: long-quantile selection."""
from __future__ import annotations

import pandas as pd


def long_quantile(
    signal: pd.Series,
    dates: pd.Series,
    quantile: float = 0.80,
) -> dict:
    """每日选出 signal 位于前 quantile 分位的股票。

    返回 {date: [index 列表]}，当日样本不足 5 只 → 空列表。
    """
    frame = pd.DataFrame({"date": dates, "signal": signal})
    picks: dict = {}
    for day, group in frame.groupby("date", sort=True):
        valid = group.dropna(subset=["signal"])
        if len(valid) < 5:
            picks[day] = []
            continue
        threshold = valid["signal"].quantile(quantile)
        picks[day] = valid.loc[
            valid["signal"] >= threshold
        ].index.tolist()
    return picks
