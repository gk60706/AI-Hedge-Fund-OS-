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


# ============================================================================
# V3.9.2 Factor Neutralization (step11 factors/neutralization.py)
#
# 主要功能：
#   1. 行业中性化
#   2. 市值中性化
#   3. 行业 + 市值联合中性化
#   4. 横截面 OLS 残差（numpy.linalg.lstsq，无 statsmodels/scipy 依赖）
#   5. 暴露度诊断
#   6. 中性化前后相关性检查
#
# 设计要点：
#   - 每个交易日独立横截面回归，不跨日期估计参数
#   - 不使用未来交易日数据
#   - 不修改原始 DataFrame
#   - 不依赖 scipy / statsmodels
# ============================================================================

from dataclasses import dataclass as _dataclass_v392
from dataclasses import field as _field_v392
from typing import (
    Any as _AnyV392,
    Dict as _DictV392,
    List as _ListV392,
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
    Tuple as _TupleV392,
)


class NeutralizationErrorV392(Exception):
    """中性化模块基础异常。"""


@_dataclass_v392
class NeutralizationConfigV392:
    """中性化配置。"""

    date_column: str = "date"
    code_column: str = "code"
    industry_column: str = "industry"
    market_cap_column: str = "market_cap"
    add_intercept: bool = True
    log_market_cap: bool = True
    min_obs: int = 20
    min_industry_obs: int = 5
    winsorize_exposure: bool = True
    winsor_limit: float = 3.0
    standardize_exposure: bool = True
    unknown_industry: str = "UNKNOWN"
    keep_original: bool = True
    output_suffix: str = "_neutral"
    metadata: _DictV392[str, _AnyV392] = _field_v392(default_factory=dict)


def _to_numeric_v392(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _safe_log_market_cap_v392(series: pd.Series) -> pd.Series:
    """对市值取自然对数，<=0 视为缺失。"""
    s = _to_numeric_v392(series)
    s = s.where(s > 0, np.nan)
    return np.log(s)


def _winsorize_v392(series: pd.Series, n_mad: float = 3.0) -> pd.Series:
    """MAD 去极值。"""
    s = _to_numeric_v392(series).copy()
    valid = s.dropna()
    if len(valid) < 2:
        return s
    median = valid.median()
    mad = np.median(np.abs(valid.to_numpy() - median))
    if not np.isfinite(mad) or mad == 0:
        return s
    scale = 1.4826 * mad
    lower = median - n_mad * scale
    upper = median + n_mad * scale
    return s.clip(lower=lower, upper=upper)


def _standardize_v392(series: pd.Series) -> pd.Series:
    """Z-score 标准化。"""
    s = _to_numeric_v392(series)
    mean = s.mean()
    std = s.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=s.index).where(s.notna(), np.nan)
    return (s - mean) / std


def industry_dummies_v392(
    series: pd.Series, *, prefix: str = "industry"
) -> pd.DataFrame:
    """行业 One-Hot 编码，drop_first=True 避免与截距项完全共线。"""
    s = series.astype("object").copy()
    s = s.where(s.notna(), "UNKNOWN")
    s = s.astype(str).str.strip().replace("", "UNKNOWN")
    dummies = pd.get_dummies(
        s, prefix=prefix, drop_first=True, dtype=float
    )
    return dummies


def cross_section_ols_residual_v392(
    y: pd.Series,
    X: pd.DataFrame,
    *,
    add_intercept: bool = True,
    min_obs: int = 20,
) -> _TupleV392[pd.Series, _DictV392[str, _AnyV392]]:
    """横截面 OLS：y = Xβ + ε，返回 ε = y - Xβ。

    参数估计仅使用当前交易日数据；使用 numpy.linalg.lstsq，
    不依赖 statsmodels/scipy。
    """
    if not isinstance(y, pd.Series):
        raise NeutralizationErrorV392("y must be pandas.Series.")
    if not isinstance(X, pd.DataFrame):
        raise NeutralizationErrorV392("X must be pandas.DataFrame.")
    if len(y) != len(X):
        raise NeutralizationErrorV392("y and X length mismatch.")

    y_num = _to_numeric_v392(y)
    X_num = X.apply(pd.to_numeric, errors="coerce")
    valid = y_num.notna() & X_num.notna().all(axis=1)
    if int(valid.sum()) < min_obs:
        residual = pd.Series(
            np.nan, index=y.index, name=y.name
        )
        return residual, {
            "status": "insufficient_observations",
            "n_obs": int(valid.sum()),
            "n_features": int(X.shape[1]),
        }

    y_valid = y_num.loc[valid]
    X_valid = X_num.loc[valid]

    matrix = X_valid.to_numpy(dtype=float)
    target = y_valid.to_numpy(dtype=float)
    if add_intercept:
        intercept = np.ones((len(matrix), 1), dtype=float)
        matrix = np.column_stack([intercept, matrix])

    try:
        beta, residuals, rank, singular_values = np.linalg.lstsq(
            matrix, target, rcond=None
        )
    except np.linalg.LinAlgError as exc:
        raise NeutralizationErrorV392("OLS regression failed.") from exc

    fitted = matrix @ beta
    residual_values = target - fitted
    residual = pd.Series(
        np.nan, index=y.index, dtype=float, name=y.name
    )
    residual.loc[valid] = residual_values

    ss_res = float(np.sum(residual_values ** 2))
    mean_y = float(np.mean(target))
    ss_tot = float(np.sum((target - mean_y) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    diagnostics = {
        "status": "ok",
        "n_obs": int(valid.sum()),
        "n_features": int(X.shape[1]),
        "matrix_rank": int(rank),
        "r2": float(r2),
        "residual_std": float(np.std(residual_values)),
    }
    return residual, diagnostics


class FactorNeutralizerV392:
    """因子中性化引擎：行业 / 市值 / 联合中性化。"""

    def __init__(
        self,
        config: _OptionalV392[NeutralizationConfigV392] = None,
    ):
        self.config = config or NeutralizationConfigV392()

    def prepare_market_cap(self, data: pd.DataFrame) -> pd.Series:
        """准备市值暴露（默认 log(market_cap)，可选 winsorize + zscore）。"""
        column = self.config.market_cap_column
        if column not in data.columns:
            raise NeutralizationErrorV392(
                f"Market cap column '{column}' not found."
            )
        result = _to_numeric_v392(data[column])
        if self.config.log_market_cap:
            result = _safe_log_market_cap_v392(result)
        if self.config.winsorize_exposure:
            result = _winsorize_v392(result, self.config.winsor_limit)
        if self.config.standardize_exposure:
            result = _standardize_v392(result)
        result.name = "log_market_cap"
        return result

    def prepare_industry(self, data: pd.DataFrame) -> pd.DataFrame:
        """准备行业虚拟变量。"""
        column = self.config.industry_column
        if column not in data.columns:
            raise NeutralizationErrorV392(
                f"Industry column '{column}' not found."
            )
        return industry_dummies_v392(data[column])

    def neutralize_cross_section(
        self,
        data: pd.DataFrame,
        factor_column: str,
        *,
        neutralize_industry: bool = True,
        neutralize_size: bool = True,
    ) -> _TupleV392[pd.Series, _DictV392[str, _AnyV392]]:
        """对一个交易日执行横截面中性化。"""
        if factor_column not in data.columns:
            raise NeutralizationErrorV392(
                f"Factor column '{factor_column}' not found."
            )
        y = _to_numeric_v392(data[factor_column])
        X_parts: _ListV392[pd.DataFrame] = []
        metadata: _DictV392[str, _AnyV392] = {
            "factor": factor_column,
            "industry": neutralize_industry,
            "size": neutralize_size,
        }

        if neutralize_industry:
            industry = self.prepare_industry(data)
            if not industry.empty:
                X_parts.append(industry)
                metadata["industry_count"] = int(industry.shape[1])

        if neutralize_size:
            size = self.prepare_market_cap(data)
            X_parts.append(size.rename("log_market_cap").to_frame())

        if not X_parts:
            return y.copy(), {**metadata, "status": "no_exposure"}

        X = pd.concat(X_parts, axis=1)
        constant_columns = [
            col
            for col in X.columns
            if X[col].nunique(dropna=True) <= 1
        ]
        if constant_columns:
            X = X.drop(columns=constant_columns)
        if X.empty:
            return y.copy(), {**metadata, "status": "no_valid_exposure"}

        residual, diagnostics = cross_section_ols_residual_v392(
            y,
            X,
            add_intercept=self.config.add_intercept,
            min_obs=self.config.min_obs,
        )
        metadata.update(diagnostics)
        return residual, metadata

    def neutralize(
        self,
        data: pd.DataFrame,
        factor_column: str,
        *,
        neutralize_industry: bool = True,
        neutralize_size: bool = True,
        output_column: _OptionalV392[str] = None,
    ) -> _TupleV392[pd.Series, pd.DataFrame]:
        """对完整 Panel 逐日横截面中性化。"""
        if not isinstance(data, pd.DataFrame):
            raise NeutralizationErrorV392("data must be DataFrame.")
        if data.empty:
            raise NeutralizationErrorV392("data is empty.")
        date_column = self.config.date_column
        if date_column not in data.columns:
            raise NeutralizationErrorV392(
                f"Date column '{date_column}' not found."
            )
        if factor_column not in data.columns:
            raise NeutralizationErrorV392(
                f"Factor column '{factor_column}' not found."
            )

        dates = pd.to_datetime(data[date_column], errors="coerce")
        working = data.copy()
        working["_normalized_date"] = dates
        working["_original_position"] = np.arange(len(working))

        results: _ListV392[pd.Series] = []
        diagnostics_rows: _ListV392[_DictV392[str, _AnyV392]] = []

        for current_date, group in working.groupby(
            "_normalized_date", sort=True, dropna=False
        ):
            if pd.isna(current_date):
                residual = pd.Series(
                    np.nan, index=group.index, dtype=float
                )
                diagnostics_rows.append(
                    {
                        "date": None,
                        "status": "invalid_date",
                        "n_rows": int(len(group)),
                    }
                )
            else:
                try:
                    residual, diagnostics = self.neutralize_cross_section(
                        group,
                        factor_column,
                        neutralize_industry=neutralize_industry,
                        neutralize_size=neutralize_size,
                    )
                    diagnostics = {
                        "date": pd.Timestamp(current_date),
                        "n_rows": int(len(group)),
                        **diagnostics,
                    }
                    diagnostics_rows.append(diagnostics)
                except Exception as exc:
                    residual = pd.Series(
                        np.nan, index=group.index, dtype=float
                    )
                    diagnostics_rows.append(
                        {
                            "date": pd.Timestamp(current_date),
                            "status": "error",
                            "error": str(exc),
                            "n_rows": int(len(group)),
                        }
                    )
            residual.name = output_column or (
                f"{factor_column}{self.config.output_suffix}"
            )
            results.append(residual)

        if results:
            residual = pd.concat(results)
        else:
            residual = pd.Series(np.nan, index=data.index)
        residual = residual.reindex(data.index)
        residual.name = output_column or (
            f"{factor_column}{self.config.output_suffix}"
        )
        diagnostics_df = pd.DataFrame(diagnostics_rows)
        return residual, diagnostics_df


def neutralize_factor_v392(
    data: pd.DataFrame,
    factor_column: str,
    *,
    industry_column: str = "industry",
    market_cap_column: str = "market_cap",
    neutralize_industry: bool = True,
    neutralize_size: bool = True,
    min_obs: int = 20,
    output_column: _OptionalV392[str] = None,
) -> _TupleV392[pd.Series, pd.DataFrame]:
    """便捷函数：一行调用完成行业+市值联合中性化。"""
    config = NeutralizationConfigV392(
        industry_column=industry_column,
        market_cap_column=market_cap_column,
        min_obs=min_obs,
    )
    neutralizer = FactorNeutralizerV392(config)
    return neutralizer.neutralize(
        data,
        factor_column,
        neutralize_industry=neutralize_industry,
        neutralize_size=neutralize_size,
        output_column=output_column,
    )


def exposure_correlation_v392(
    data: pd.DataFrame,
    factor_column: str,
    exposure_columns: _SequenceV392[str],
) -> pd.DataFrame:
    """计算因子与暴露变量的 Pearson 相关性。"""
    columns = [factor_column, *exposure_columns]
    missing = [c for c in columns if c not in data.columns]
    if missing:
        raise NeutralizationErrorV392(f"Missing columns: {missing}")
    frame = data[columns].copy()
    for column in columns:
        frame[column] = _to_numeric_v392(frame[column])
    return frame.corr(method="pearson")


def residual_exposure_check_v392(
    data: pd.DataFrame,
    original_factor: str,
    neutral_factor: str,
    exposure_columns: _SequenceV392[str],
) -> pd.DataFrame:
    """对比中性化前后与暴露变量的相关性。"""
    rows = []
    for exposure in exposure_columns:
        if exposure not in data.columns:
            continue
        original_corr = (
            data[[original_factor, exposure]].corr().iloc[0, 1]
        )
        neutral_corr = (
            data[[neutral_factor, exposure]].corr().iloc[0, 1]
        )
        rows.append(
            {
                "exposure": exposure,
                "original_corr": (
                    float(original_corr)
                    if pd.notna(original_corr)
                    else np.nan
                ),
                "neutral_corr": (
                    float(neutral_corr)
                    if pd.notna(neutral_corr)
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)
