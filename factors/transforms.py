"""V3.9.1 cross-sectional transforms (dates-grouped)."""
from __future__ import annotations

import pandas as pd


def winsorize_cs(series: pd.Series, dates: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """按 date 分组逐组 winsorize。"""
    frame = pd.DataFrame({"date": dates, "value": series})
    out = []
    for _, group in frame.groupby("date", sort=False):
        out.append(group["value"].clip(
            group["value"].quantile(lower),
            group["value"].quantile(upper),
        ))
    if not out:
        return pd.Series(index=series.index, dtype="float64")
    return pd.concat(out).reindex(series.index)


def rank_cs(series: pd.Series, dates: pd.Series) -> pd.Series:
    """按 date 分组横截面排名（pct=True）。"""
    frame = pd.DataFrame({"date": dates, "value": series})
    return (
        frame.groupby("date")["value"]
        .rank(pct=True, method="average")
        .reset_index(drop=True)
    )


def zscore_cs(series: pd.Series, dates: pd.Series) -> pd.Series:
    """按 date 分组横截面 z-score。"""
    frame = pd.DataFrame({"date": dates, "value": series})
    grouped = frame.groupby("date")["value"]
    mean = grouped.transform("mean")
    std = grouped.transform("std", ddof=0)
    out = (frame["value"] - mean) / std
    out[std == 0] = float("nan")
    return out.reset_index(drop=True)
