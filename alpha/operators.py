from __future__ import annotations

import numpy as np
import pandas as pd


class AlphaOperators:
    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def sub(a, b):
        return a - b

    @staticmethod
    def mul(a, b):
        return a * b

    @staticmethod
    def div(a, b):
        denominator = b.replace(0, np.nan)
        return a / denominator

    @staticmethod
    def neg(a):
        return -a

    @staticmethod
    def abs(a):
        return a.abs()

    @staticmethod
    def log(a):
        return np.log(a.abs() + 1e-8)

    @staticmethod
    def rank(a):
        return a.rank(pct=True)

    @staticmethod
    def zscore(a):
        std = a.std()
        if std == 0 or np.isnan(std):
            return a * 0
        return (a - a.mean()) / std
# ============================================================================
# V3.9.1 unified research engine - operators (v391 naming to avoid V3.9 conflict)
# ============================================================================


def apply_operator_v391(operator: str, args: list, dates=None):
    """V3.9.1 operator dispatch: lowercase names + (operator, args, dates)."""
    a = args[0]
    if operator == "neg":
        return -a
    if operator == "abs":
        return a.abs()
    if operator == "log":
        return np.log(a.abs().replace(0, np.nan))
    if operator == "rank":
        if dates is None:
            raise ValueError("rank 需要 dates")
        return a.groupby(dates).rank(pct=True)
    if operator == "zscore":
        if dates is None:
            raise ValueError("zscore 需要 dates")
        return a.groupby(dates).transform(
            lambda x: (x - x.mean()) / (x.std(ddof=0) if x.std(ddof=0) > 0 else np.nan)
        )
    b = args[1]
    if operator == "add":
        return a + b
    if operator == "sub":
        return a - b
    if operator == "mul":
        return a * b
    if operator == "div":
        return safe_div(a, b)
    raise ValueError(f"未知 operator: {operator}")
