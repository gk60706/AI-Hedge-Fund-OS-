"""V3.9.1 drawdown helper."""
from __future__ import annotations

import pandas as pd


def max_drawdown(equity) -> float:
    """最大回撤：equity 序列中 (value / cummax - 1) 的最小值。"""
    series = pd.Series(equity).dropna()
    if len(series) < 2:
        return 0.0
    return float((series / series.cummax() - 1.0).min())
