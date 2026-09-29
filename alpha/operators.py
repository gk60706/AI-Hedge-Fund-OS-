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

# ============================================================
# V3.9.2 Alpha Operators (appended, V392)
# ============================================================

from typing import Callable

OperatorFunction = Callable[..., pd.Series]
# ============================================================
# V392 helpers
# ============================================================
def _as_numeric_v392(value: pd.Series, index: pd.Index | None = None) -> pd.Series:
    if not isinstance(value, pd.Series):
        value = pd.Series(value, index=index, dtype="float64")
    return pd.to_numeric(value, errors="coerce").astype("float64")


def _safe_divide_v392(numerator: pd.Series, denominator: pd.Series,
                      *, epsilon: float = 1e-12) -> pd.Series:
    numerator = _as_numeric_v392(numerator)
    denominator = _as_numeric_v392(denominator, numerator.index)
    denominator = denominator.where(denominator.abs() > epsilon)
    result = numerator / denominator
    return result.replace([np.inf, -np.inf], np.nan)
# ============================================================
# V392 basic arithmetic
# ============================================================
def op_add(left: pd.Series, right: pd.Series) -> pd.Series:
    return (_as_numeric_v392(left) + _as_numeric_v392(right, left.index)).replace(
        [np.inf, -np.inf], np.nan
    )


def op_sub(left: pd.Series, right: pd.Series) -> pd.Series:
    return (_as_numeric_v392(left) - _as_numeric_v392(right, left.index)).replace(
        [np.inf, -np.inf], np.nan
    )


def op_mul(left: pd.Series, right: pd.Series) -> pd.Series:
    return (_as_numeric_v392(left) * _as_numeric_v392(right, left.index)).replace(
        [np.inf, -np.inf], np.nan
    )


def op_div(left: pd.Series, right: pd.Series) -> pd.Series:
    return _safe_divide_v392(left, right)


def op_neg(value: pd.Series) -> pd.Series:
    return -_as_numeric_v392(value)


def op_abs(value: pd.Series) -> pd.Series:
    return _as_numeric_v392(value).abs()


def op_sign(value: pd.Series) -> pd.Series:
    return np.sign(_as_numeric_v392(value))
# ============================================================
# V392 mathematical transforms
# ============================================================
def op_log(value: pd.Series) -> pd.Series:
    """
    安全 log：

    log(abs(x) + epsilon)

    """
    x = _as_numeric_v392(value)
    result = np.log(x.abs() + 1e-12)
    return pd.Series(result, index=x.index).replace([np.inf, -np.inf], np.nan)


def op_sqrt(value: pd.Series) -> pd.Series:
    x = _as_numeric_v392(value)
    result = np.sqrt(x.abs())
    return pd.Series(result, index=x.index).replace([np.inf, -np.inf], np.nan)


def op_inv(value: pd.Series) -> pd.Series:
    return _safe_divide_v392(pd.Series(1.0, index=value.index), value)


def op_clip(value: pd.Series, lower: float = -5.0, upper: float = 5.0) -> pd.Series:
    return _as_numeric_v392(value).clip(lower=lower, upper=upper)
# ============================================================
# V392 cross-sectional operators
# ============================================================
def op_rank(value: pd.Series, dates: pd.Series | None = None) -> pd.Series:
    """
    横截面 Rank。

    """
    x = _as_numeric_v392(value)
    if dates is None:
        return x.rank(method="average", pct=True)
    date_values = pd.to_datetime(dates, errors="coerce")
    result = (x.groupby(date_values, group_keys=False).rank(method="average", pct=True))
    return result


def op_zscore(value: pd.Series, dates: pd.Series | None = None) -> pd.Series:
    """
    横截面 Z-Score。

    """
    x = _as_numeric_v392(value)
    if dates is None:
        mean = x.mean()
        std = x.std(ddof=0)
        if pd.isna(std) or std < 1e-12:
            return pd.Series(0.0, index=x.index)
        return (x - mean) / std

    def _zscore(group: pd.Series) -> pd.Series:
        std = group.std(ddof=0)
        if pd.isna(std) or std < 1e-12:
            return pd.Series(0.0, index=group.index)
        return (group - group.mean()) / std

    date_values = pd.to_datetime(dates, errors="coerce")
    result = (x.groupby(date_values, group_keys=False).apply(_zscore))
    return result.reindex(x.index)


def op_winsorize(value: pd.Series, dates: pd.Series | None = None,
                 lower_quantile: float = 0.01,
                 upper_quantile: float = 0.99) -> pd.Series:
    """
    横截面 winsorization。

    """
    x = _as_numeric_v392(value)
    lower_quantile = float(lower_quantile)
    upper_quantile = float(upper_quantile)
    if not (0 <= lower_quantile < upper_quantile <= 1):
        raise ValueError("Invalid winsorization quantiles.")
    if dates is None:
        low = x.quantile(lower_quantile)
        high = x.quantile(upper_quantile)
        return x.clip(low, high)

    def _clip(group: pd.Series) -> pd.Series:
        low = group.quantile(lower_quantile)
        high = group.quantile(upper_quantile)
        return group.clip(low, high)

    date_values = pd.to_datetime(dates, errors="coerce")
    result = (x.groupby(date_values, group_keys=False).apply(_clip))
    return result.reindex(x.index)
# ============================================================
# V392 operator registry
# ============================================================
OPERATORS: dict[str, OperatorFunction] = {
    "add": op_add, "sub": op_sub, "mul": op_mul, "div": op_div,
    "neg": op_neg, "abs": op_abs, "sign": op_sign,
    "log": op_log, "sqrt": op_sqrt, "inv": op_inv, "clip": op_clip,
    "rank": op_rank, "zscore": op_zscore, "winsorize": op_winsorize,
}
# ============================================================
# V392 arity
# ============================================================
OPERATOR_ARITY: dict[str, int | tuple[int, int]] = {
    "add": 2, "sub": 2, "mul": 2, "div": 2,
    "neg": 1, "abs": 1, "sign": 1,
    "log": 1, "sqrt": 1, "inv": 1, "clip": 1,
    "rank": 1, "zscore": 1, "winsorize": 1,
}
# ============================================================
# V392 public helpers
# ============================================================
def get_operator(name: str) -> OperatorFunction:
    name = name.lower().strip()
    if name not in OPERATORS:
        raise KeyError(f"Unknown alpha operator: {name}")
    return OPERATORS[name]


def get_operator_arity(name: str) -> int | tuple[int, int]:
    name = name.lower().strip()
    if name not in OPERATOR_ARITY:
        raise KeyError(f"Unknown alpha operator: {name}")
    return OPERATOR_ARITY[name]


def is_unary_operator(name: str) -> bool:
    arity = get_operator_arity(name)
    return isinstance(arity, int) and arity == 1


def is_binary_operator(name: str) -> bool:
    arity = get_operator_arity(name)
    return isinstance(arity, int) and arity == 2


__all__ = [
    "OperatorFunction", "OPERATORS", "OPERATOR_ARITY",
    "get_operator", "get_operator_arity", "is_unary_operator", "is_binary_operator",
    "op_add", "op_sub", "op_mul", "op_div", "op_neg", "op_abs", "op_sign",
    "op_log", "op_sqrt", "op_inv", "op_clip", "op_rank", "op_zscore", "op_winsorize",
]

