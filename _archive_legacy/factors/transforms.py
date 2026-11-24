"""V3.9.1 cross-sectional transforms (dates-grouped)."""
from __future__ import annotations

import pandas as pd
import numpy as np


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


# ============================================================================
# V3.9.2 Factor Transforms (step10 factors/transforms.py)
#
# 设计原则：
#   1. 所有横截面操作必须按 date 分组
#   2. 不使用未来日期的数据计算当前日期因子
#   3. 不修改原始 DataFrame
#   4. 尽量保持 index 对齐
#
# 与旧版 winsorize_cs/rank_cs/zscore_cs 的关系：
#   - 旧版函数保留（V3.9.1 横截面版本）
#   - 新版统一加 V392 后缀，包含 winsorize/rank/zscore/minmax/
#     rank_normalize/CrossSectionTransformer/TransformPipeline 完整管线
# ============================================================================

from dataclasses import dataclass as _dataclass_v392
from typing import (
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
)


class TransformErrorV392(Exception):
    """因子变换异常。"""


@_dataclass_v392
class TransformConfigV392:
    """因子变换配置。"""

    winsorize: bool = True
    winsor_method: str = "mad"
    winsor_limit: float = 3.0
    standardize: bool = True
    standardize_method: str = "zscore"
    rank_pct: bool = True
    fill_method: _OptionalV392[str] = None
    min_obs: int = 3
    date_column: str = "date"
    code_column: str = "code"


def _validate_series_v392(series: pd.Series) -> pd.Series:
    if not isinstance(series, pd.Series):
        raise TransformErrorV392("Input must be pandas.Series.")
    return pd.to_numeric(series, errors="coerce")


def _validate_dataframe_v392(data: pd.DataFrame) -> None:
    if not isinstance(data, pd.DataFrame):
        raise TransformErrorV392("Input must be pandas.DataFrame.")
    if data.empty:
        raise TransformErrorV392("Input DataFrame is empty.")


def fill_missing_v392(
    series: pd.Series,
    method: _OptionalV392[str] = None,
) -> pd.Series:
    """全局缺失值处理（median/mean/zero）。横截面研究推荐 fill_missing_by_date_v392。"""
    s = _validate_series_v392(series).copy()
    if method is None:
        return s
    method = method.lower()
    if method == "median":
        median = s.median()
        if pd.notna(median):
            s = s.fillna(median)
    elif method == "mean":
        mean = s.mean()
        if pd.notna(mean):
            s = s.fillna(mean)
    elif method == "zero":
        s = s.fillna(0.0)
    else:
        raise TransformErrorV392(f"Unknown missing value method: {method}")
    return s


def fill_missing_by_date_v392(
    data: pd.DataFrame,
    column: str,
    method: str = "median",
    date_column: str = "date",
) -> pd.Series:
    """按交易日横截面填充缺失值（不跨日期，防未来数据泄漏）。"""
    _validate_dataframe_v392(data)
    if column not in data.columns:
        raise TransformErrorV392(f"Column '{column}' not found.")
    if date_column not in data.columns:
        raise TransformErrorV392(f"Date column '{date_column}' not found.")
    s = pd.to_numeric(data[column], errors="coerce")
    dates = pd.to_datetime(data[date_column], errors="coerce")
    result = s.copy()
    temp = pd.DataFrame({"_value": s, "_date": dates}, index=data.index)
    if method == "median":
        values = temp.groupby("_date", sort=False, dropna=False)["_value"].transform(
            lambda x: x.fillna(x.median())
        )
    elif method == "mean":
        values = temp.groupby("_date", sort=False, dropna=False)["_value"].transform(
            lambda x: x.fillna(x.mean())
        )
    elif method == "zero":
        values = temp["_value"].fillna(0.0)
    else:
        raise TransformErrorV392(f"Unsupported method: {method}")
    result.loc[:] = values
    return result


def winsorize_quantile_v392(
    series: pd.Series, lower: float = 0.01, upper: float = 0.99
) -> pd.Series:
    """分位数去极值。"""
    s = _validate_series_v392(series).copy()
    if not 0 <= lower < upper <= 1:
        raise TransformErrorV392("Require 0 <= lower < upper <= 1.")
    valid = s.dropna()
    if len(valid) == 0:
        return s
    low = valid.quantile(lower)
    high = valid.quantile(upper)
    return s.clip(lower=low, upper=high)


def winsorize_mad_v392(series: pd.Series, n_mad: float = 3.0) -> pd.Series:
    """MAD 去极值（median ± n_mad * 1.4826 * MAD）。"""
    s = _validate_series_v392(series).copy()
    valid = s.dropna()
    if len(valid) == 0:
        return s
    median = valid.median()
    mad = np.median(np.abs(valid.to_numpy() - median))
    if not np.isfinite(mad):
        return s
    if mad == 0:
        return s
    scale = 1.4826 * mad
    return s.clip(lower=median - n_mad * scale, upper=median + n_mad * scale)


def winsorize_v392(
    series: pd.Series, method: str = "mad", limit: float = 3.0
) -> pd.Series:
    """通用去极值入口（mad / quantile）。"""
    method = method.lower()
    if method == "mad":
        return winsorize_mad_v392(series, n_mad=limit)
    if method == "quantile":
        q = min(max(0.005, 1.0 / (limit * 10.0)), 0.20)
        return winsorize_quantile_v392(series, lower=q, upper=1.0 - q)
    raise TransformErrorV392(f"Unknown winsorize method: {method}")


def winsorize_by_date_v392(
    data: pd.DataFrame,
    column: str,
    *,
    date_column: str = "date",
    method: str = "mad",
    limit: float = 3.0,
) -> pd.Series:
    """按交易日横截面去极值（A股因子研究最重要版本）。"""
    _validate_dataframe_v392(data)
    if column not in data.columns:
        raise TransformErrorV392(f"Column '{column}' not found.")
    if date_column not in data.columns:
        raise TransformErrorV392(f"Column '{date_column}' not found.")
    dates = pd.to_datetime(data[date_column], errors="coerce")
    values = pd.to_numeric(data[column], errors="coerce")
    temp = pd.DataFrame({"_date": dates, "_value": values}, index=data.index)
    result = temp.groupby("_date", sort=False, dropna=False)["_value"].transform(
        lambda x: winsorize_v392(x, method=method, limit=limit)
    )
    result.index = data.index
    return result


def rank_v392(
    series: pd.Series, pct: bool = True, ascending: bool = True
) -> pd.Series:
    """普通排名（pct=True → [0,1]）。"""
    s = _validate_series_v392(series)
    return s.rank(method="average", pct=pct, ascending=ascending)


def rank_centered_v392(series: pd.Series) -> pd.Series:
    """将 rank 居中到 [-0.5, 0.5]。"""
    return rank_v392(series) - 0.5


def rank_by_date_v392(
    data: pd.DataFrame,
    column: str,
    *,
    date_column: str = "date",
    ascending: bool = True,
) -> pd.Series:
    """横截面 Rank（每个交易日单独排名）。"""
    _validate_dataframe_v392(data)
    if column not in data.columns:
        raise TransformErrorV392(f"Column '{column}' not found.")
    if date_column not in data.columns:
        raise TransformErrorV392(f"Column '{date_column}' not found.")
    values = pd.to_numeric(data[column], errors="coerce")
    dates = pd.to_datetime(data[date_column], errors="coerce")
    temp = pd.DataFrame({"_date": dates, "_value": values}, index=data.index)
    result = temp.groupby("_date", sort=False, dropna=False)["_value"].transform(
        lambda x: x.rank(method="average", pct=True, ascending=ascending)
    )
    result.index = data.index
    return result


def zscore_v392(series: pd.Series, ddof: int = 0) -> pd.Series:
    """标准 Z-Score：z = (x - mean) / std。"""
    s = _validate_series_v392(series)
    mean = s.mean()
    std = s.std(ddof=ddof)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=s.index, name=s.name).where(s.notna(), np.nan)
    return (s - mean) / std


def robust_zscore_v392(series: pd.Series) -> pd.Series:
    """Robust Z-Score（median + MAD，对极端值更稳健）。"""
    s = _validate_series_v392(series)
    median = s.median()
    mad = np.median(np.abs(s.dropna().to_numpy() - median))
    if pd.isna(mad) or mad == 0:
        return pd.Series(0.0, index=s.index, name=s.name).where(s.notna(), np.nan)
    return (s - median) / (1.4826 * mad)


def zscore_by_date_v392(
    data: pd.DataFrame,
    column: str,
    *,
    date_column: str = "date",
    ddof: int = 0,
) -> pd.Series:
    """横截面 Z-Score（每个交易日独立计算）。"""
    _validate_dataframe_v392(data)
    if column not in data.columns:
        raise TransformErrorV392(f"Column '{column}' not found.")
    if date_column not in data.columns:
        raise TransformErrorV392(f"Column '{date_column}' not found.")
    values = pd.to_numeric(data[column], errors="coerce")
    dates = pd.to_datetime(data[date_column], errors="coerce")
    temp = pd.DataFrame({"_date": dates, "_value": values}, index=data.index)
    group = temp.groupby("_date", sort=False, dropna=False)["_value"]
    means = group.transform("mean")
    stds = group.transform(lambda x: x.std(ddof=ddof))
    result = (values - means) / stds.replace(0, np.nan)
    result = result.where(stds.ne(0), 0.0)
    result = result.where(values.notna(), np.nan)
    result.index = data.index
    return result


def robust_zscore_by_date_v392(
    data: pd.DataFrame,
    column: str,
    *,
    date_column: str = "date",
) -> pd.Series:
    """横截面 Robust Z-Score。"""
    _validate_dataframe_v392(data)
    if column not in data.columns:
        raise TransformErrorV392(f"Column '{column}' not found.")
    if date_column not in data.columns:
        raise TransformErrorV392(f"Column '{date_column}' not found.")
    dates = pd.to_datetime(data[date_column], errors="coerce")
    values = pd.to_numeric(data[column], errors="coerce")
    temp = pd.DataFrame({"_date": dates, "_value": values}, index=data.index)
    result = temp.groupby("_date", sort=False, dropna=False)["_value"].transform(
        robust_zscore_v392
    )
    result.index = data.index
    return result


def minmax_v392(series: pd.Series) -> pd.Series:
    """Min-Max：(x - min) / (max - min)。"""
    s = _validate_series_v392(series)
    low = s.min()
    high = s.max()
    if pd.isna(low) or pd.isna(high):
        return s * np.nan
    if high == low:
        return pd.Series(0.5, index=s.index, name=s.name).where(s.notna(), np.nan)
    return (s - low) / (high - low)


def minmax_by_date_v392(
    data: pd.DataFrame,
    column: str,
    *,
    date_column: str = "date",
) -> pd.Series:
    """横截面 Min-Max。"""
    dates = pd.to_datetime(data[date_column], errors="coerce")
    values = pd.to_numeric(data[column], errors="coerce")
    temp = pd.DataFrame({"_date": dates, "_value": values}, index=data.index)
    result = temp.groupby("_date", sort=False, dropna=False)["_value"].transform(minmax_v392)
    result.index = data.index
    return result


def rank_normalize_v392(series: pd.Series) -> pd.Series:
    """Rank Normalize 到 [-1, 1]（不依赖 scipy）。"""
    s = _validate_series_v392(series)
    r = s.rank(method="average", pct=True)
    return 2.0 * (r - 0.5)


def rank_normalize_by_date_v392(
    data: pd.DataFrame,
    column: str,
    *,
    date_column: str = "date",
) -> pd.Series:
    """横截面 Rank Normalize。"""
    dates = pd.to_datetime(data[date_column], errors="coerce")
    values = pd.to_numeric(data[column], errors="coerce")
    temp = pd.DataFrame({"_date": dates, "_value": values}, index=data.index)
    result = temp.groupby("_date", sort=False, dropna=False)["_value"].transform(
        rank_normalize_v392
    )
    result.index = data.index
    return result


class CrossSectionTransformerV392:
    """横截面因子变换器（Missing → Winsorize → Rank → Standardize）。"""

    def __init__(
        self,
        *,
        winsorize_enabled: bool = True,
        winsor_method: str = "mad",
        winsor_limit: float = 3.0,
        standardize_enabled: bool = True,
        standardize_method: str = "zscore",
        rank_first: bool = False,
        centered_rank: bool = False,
        fill_method: _OptionalV392[str] = None,
        date_column: str = "date",
    ):
        self.winsorize_enabled = winsorize_enabled
        self.winsor_method = winsor_method
        self.winsor_limit = winsor_limit
        self.standardize_enabled = standardize_enabled
        self.standardize_method = standardize_method
        self.rank_first = rank_first
        self.centered_rank = centered_rank
        self.fill_method = fill_method
        self.date_column = date_column

    def transform(
        self, data: pd.DataFrame, column: str
    ) -> pd.Series:
        """执行完整横截面变换。"""
        _validate_dataframe_v392(data)
        if column not in data.columns:
            raise TransformErrorV392(f"Column '{column}' not found.")

        # Missing
        if self.fill_method is not None:
            values = fill_missing_by_date_v392(
                data,
                column,
                method=self.fill_method,
                date_column=self.date_column,
            )
            temp = data.copy()
            temp[column] = values
        else:
            temp = data

        # Winsorize
        if self.winsorize_enabled:
            values = winsorize_by_date_v392(
                temp,
                column,
                date_column=self.date_column,
                method=self.winsor_method,
                limit=self.winsor_limit,
            )
        else:
            values = pd.to_numeric(temp[column], errors="coerce")
        temp = temp.copy()
        temp[column] = values

        # Rank
        if self.rank_first:
            values = rank_by_date_v392(
                temp, column, date_column=self.date_column
            )
            if self.centered_rank:
                values = values - 0.5
            temp[column] = values

        # Standardize
        if self.standardize_enabled:
            method = self.standardize_method.lower()
            if method == "zscore":
                values = zscore_by_date_v392(
                    temp, column, date_column=self.date_column
                )
            elif method == "robust_zscore":
                values = robust_zscore_by_date_v392(
                    temp, column, date_column=self.date_column
                )
            elif method == "minmax":
                values = minmax_by_date_v392(
                    temp, column, date_column=self.date_column
                )
            elif method == "rank":
                values = rank_by_date_v392(
                    temp, column, date_column=self.date_column
                )
            elif method == "rank_normalize":
                values = rank_normalize_by_date_v392(
                    temp, column, date_column=self.date_column
                )
            else:
                raise TransformErrorV392(
                    f"Unknown standardize method: {self.standardize_method}"
                )
        return values.rename(column)


class TransformPipelineV392:
    """因子变换 Pipeline（多个因子批量处理，原始字段保留）。"""

    def __init__(
        self,
        transformer: _OptionalV392[CrossSectionTransformerV392] = None,
    ):
        self.transformer = transformer or CrossSectionTransformerV392()

    def transform(
        self,
        data: pd.DataFrame,
        columns: _SequenceV392[str],
        *,
        suffix: str = "_transformed",
    ) -> pd.DataFrame:
        """批量变换因子，新增 `{column}{suffix}` 列。"""
        result = data.copy()
        for column in columns:
            transformed = self.transformer.transform(result, column)
            result[f"{column}{suffix}"] = transformed
        return result


def cross_section_summary_v392(
    data: pd.DataFrame,
    column: str,
    *,
    date_column: str = "date",
) -> pd.DataFrame:
    """输出每日横截面统计（count/mean/std/min/max/missing）。"""
    if column not in data.columns:
        raise TransformErrorV392(f"Column '{column}' not found.")
    temp = data.copy()
    temp[date_column] = pd.to_datetime(temp[date_column], errors="coerce")
    temp[column] = pd.to_numeric(temp[column], errors="coerce")
    grouped = temp.groupby(date_column, sort=True)[column]
    summary = grouped.agg(["count", "mean", "std", "min", "max"])
    summary["missing"] = temp.groupby(date_column)[column].apply(
        lambda x: int(x.isna().sum())
    )
    return summary
