"""V3.9.1 factor neutralization: group-neutral and market-cap neutral."""
from __future__ import annotations

import numpy as np
import pandas as pd


def neutralize_by_group(
    factor: pd.Series,
    group: pd.Series,
) -> pd.Series:
    """组内去均值（组内中心化）。"""
    frame = pd.DataFrame({"factor": factor, "group": group})
    mean = frame.groupby("group")["factor"].transform("mean")
    return frame["factor"] - mean


def neutralize_market_cap(
    factor: pd.Series,
    market_cap: pd.Series,
) -> pd.Series:
    """对 log(market_cap) 做最小二乘回归，返回残差。"""
    cap = pd.to_numeric(market_cap, errors="coerce")
    log_cap = np.log(cap.replace(0, np.nan))
    valid = log_cap.notna() & factor.notna()
    x = log_cap[valid].to_numpy(dtype=float)
    y = factor[valid].to_numpy(dtype=float)
    if len(x) < 3:
        return factor * float("nan")
    x1 = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(x1, y, rcond=None)
    resid = y - x1 @ coef
    out = pd.Series(float("nan"), index=factor.index)
    out[valid] = resid
    return out
