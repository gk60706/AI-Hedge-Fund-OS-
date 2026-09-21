"""
AI Hedge Fund OS
Alpha Metrics Engine
-
V3.9.2
功能：
1
.
Cross
-
sectional IC
2
.
Rank IC
3
.
ICIR
4
.
IC均值
/
标准差
5
.
IC正值比例
/
负值比例
6
.
Quantile Portfolio Q1
~
Qn
7
.
Q5
-
Q1
/
High
-
Low Spread
8
.
Long
-
only
/
Long
-
short Turnover
9
.
Signal Autocorrelation
10
.
Time
-
series performance metrics
11
.
Alpha综合评价
设计原则：
-
不自动使用 abs
(
IC
)
-
保留 Alpha 的原始方向
-
所有横截面统计按 date 分组
-
不允许未来数据进入 metrics
-
不负责生成 forward return
-
forward return 应由 backtest
/
returns
.
py 提供
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd


# ============================================================
# Exceptions
# ============================================================
class AlphaMetricsErrorV392(Exception):
    """Alpha metrics 基础异常。"""


class AlphaMetricsInputErrorV392(AlphaMetricsErrorV392):
    """输入数据错误。"""

    # ============================================================
    # Configuration
    # ============================================================


@dataclass
class AlphaMetricsConfigV392:
    """
    Alpha Metrics 配置。
    """

    date_column: str = "date"
    code_column: str = "code"
    signal_column: str = "signal"
    forward_return_column: str = "forward_return"
    quantiles: int = 5
    min_obs: int = 10
    # IC 使用 Pearson correlation
    ic_method: str = "pearson"
    # Rank IC 使用 rank 后 Pearson
    rank_ic_method: str = "spearman"
    # std 使用 sample std
    ic_std_ddof: int = 1
    # Top quantile 用于 long-only
    long_quantile: Optional[int] = None
    # Long-short 是否使用 bottom + top
    long_short: bool = True
    # 是否检查未来日期
    enforce_datetime: bool = True
    # 年化交易日
    annualization: int = 252
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.quantiles < 2:
            raise ValueError("quantiles 必须 >= 2")
            if self.min_obs < 2:
                raise ValueError("min_obs 必须 >= 2")
                if self.ic_std_ddof < 0:
                    raise ValueError("ic_std_ddof 不能小于 0")
                    if self.annualization <= 0:
                        raise ValueError("annualization 必须 > 0")
                        if self.long_quantile is None:
                            self.long_quantile = self.quantiles
                            if not 1 <= self.long_quantile <= self.quantiles:
                                raise ValueError(
                                    f"long_quantile 必须位于 1 ~ {self .quantiles} "
                                )
                                # ============================================================
                                # Result Object
                                # ============================================================


@dataclass
class AlphaMetricsResultV392:
    """
    Alpha Metrics 结果。
    summary
    :
    汇总指标
    ic_series_v392
    :
    每个交易日的 IC
    rank_ic_series_v392
    :
    每个交易日的 Rank IC
    quantile_returns
    :
    每日 Q1
    ~
    Qn 收益
    turnover_series
    :
    每日组合换手
    diagnostics
    :
    诊断信息
    """

    summary: Dict[str, float]
    ic_series_v392: pd.Series
    rank_ic_series_v392: pd.Series
    quantile_returns: pd.DataFrame
    turnover_series: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    signal_autocorrelation: float = np.nan
    diagnostics: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        result = dict(self.summary)
        result["signal_autocorrelation"] = self.signal_autocorrelation
        return result

    def summary_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "metric": list(self.summary.keys()),
                "value": list(self.summary.values()),
            }
        )
        # ============================================================
        # Utility Functions
        # ============================================================


def _ensure_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise AlphaMetricsInputErrorV392("metrics 输入必须是 pandas.DataFrame")
    if data.empty:
        raise AlphaMetricsInputErrorV392("metrics 输入 DataFrame 为空")
    return data.copy()


def _ensure_columns(
    data: pd.DataFrame,
    columns: Sequence[str],
):
    missing = [c for c in columns if c not in data.columns]
    if missing:
        raise AlphaMetricsInputErrorV392(f"缺少必要字段: {missing} ")


def _normalize_dates(
    data: pd.DataFrame,
    date_column: str,
) -> pd.DataFrame:
    df = data.copy()
    df[date_column] = pd.to_datetime(
        df[date_column],
        errors="coerce",
    )
    if df[date_column].isna().any():
        raise AlphaMetricsInputErrorV392(f" {date_column} 存在无法解析的日期")
    return df


def _prepare_data(
    data: pd.DataFrame,
    config: AlphaMetricsConfigV392,
) -> pd.DataFrame:
    df = _ensure_dataframe(data)
    _ensure_columns(
        df,
        [
            config.date_column,
            config.code_column,
            config.signal_column,
            config.forward_return_column,
        ],
    )
    df = _normalize_dates(
        df,
        config.date_column,
    )
    df[config.signal_column] = pd.to_numeric(
        df[config.signal_column],
        errors="coerce",
    )
    df[config.forward_return_column] = pd.to_numeric(
        df[config.forward_return_column],
        errors="coerce",
    )
    # 一个股票一个日期只能存在一个观测
    duplicated = df.duplicated(
        subset=[
            config.date_column,
            config.code_column,
        ],
        keep=False,
    )
    if duplicated.any():
        raise AlphaMetricsInputErrorV392("发现重复 date + code 观测，" "请先去重或聚合")
    df = df.sort_values(
        [
            config.date_column,
            config.code_column,
        ]
    ).reset_index(drop=True)
    return df


def _valid_pair(
    signal: pd.Series,
    target: pd.Series,
) -> Tuple[pd.Series, pd.Series]:
    mask = signal.notna() & target.notna() & np.isfinite(signal) & np.isfinite(target)
    return (
        signal.loc[mask],
        target.loc[mask],
    )


def _safe_corr(
    x: pd.Series,
    y: pd.Series,
) -> float:
    x, y = _valid_pair(x, y)
    if len(x) < 2:
        return np.nan
    if x.nunique(dropna=True) <= 1:
        return np.nan
    if y.nunique(dropna=True) <= 1:
        return np.nan
    value = np.corrcoef(
        x.to_numpy(dtype=float),
        y.to_numpy(dtype=float),
    )[0, 1]
    if not np.isfinite(value):
        return np.nan
    return float(value)
                    # ============================================================
                    # IC
                    # ============================================================


def cross_sectional_ic(
    signal: pd.Series,
    forward_return: pd.Series,
) -> float:
    """
    计算单个横截面的 Pearson IC。
    """
    return _safe_corr(
        signal,
        forward_return,
    )


def cross_sectional_rank_ic(
    signal: pd.Series,
    forward_return: pd.Series,
) -> float:
    """
    计算单个横截面的 Rank IC。
    不依赖 scipy。
    """
    signal_rank = signal.rank(method="average")
    return _safe_corr(
        signal_rank,
        forward_return.rank(method="average"),
    )
    # ============================================================
    # IC Series
    # ============================================================


def compute_ic_series(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> pd.Series:
    config = config or AlphaMetricsConfigV392()
    df = _prepare_data(
        data,
        config,
    )
    values = []
    for date, group in df.groupby(
        config.date_column,
        sort=True,
    ):
        signal = group[config.signal_column]
        target = group[config.forward_return_column]
        signal, target = _valid_pair(
            signal,
            target,
        )
        if len(signal) < config.min_obs:
            values.append((date, np.nan))
            continue
        ic = cross_sectional_ic(
            signal,
            target,
        )
        values.append((date, ic))
    if not values:
        return pd.Series(
            dtype=float,
            name="IC",
        )
    result = pd.Series(
        data=[value for _, value in values],
        index=[date for date, _ in values],
        name="IC",
        dtype=float,
    )
    result.index.name = config.date_column
    return result


def compute_rank_ic_series(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> pd.Series:
    config = config or AlphaMetricsConfigV392()
    df = _prepare_data(
        data,
        config,
    )
    values = []
    for date, group in df.groupby(
        config.date_column,
        sort=True,
    ):
        signal = group[config.signal_column]
        target = group[config.forward_return_column]
        signal, target = _valid_pair(
            signal,
            target,
        )
        if len(signal) < config.min_obs:
            values.append((date, np.nan))
            continue
        rank_ic = cross_sectional_rank_ic(
            signal,
            target,
        )
        values.append((date, rank_ic))
    result = pd.Series(
        data=[value for _, value in values],
        index=[date for date, _ in values],
        name="RankIC",
        dtype=float,
    )
    result.index.name = config.date_column
    return result
            # ============================================================
            # IC Summary
            # ============================================================


def summarize_ic(
    ic_series_v392: pd.Series,
    ddof: int = 1,
) -> Dict[str, float]:
    series = pd.to_numeric(
        ic_series_v392,
        errors="coerce",
    ).dropna()
    if series.empty:
        return {
            "ic_mean": np.nan,
            "ic_std": np.nan,
            "ic_ir": np.nan,
            "ic_positive_ratio": np.nan,
            "ic_negative_ratio": np.nan,
            "ic_abs_mean": np.nan,
            "ic_count": 0,
        }
    mean_ic = float(series.mean())
    std_ic = float(series.std(ddof=ddof))
    if std_ic > 0 and np.isfinite(std_ic):
        ic_ir = mean_ic / std_ic
    else:
        ic_ir = np.nan
    return {
        "ic_mean": mean_ic,
        "ic_std": std_ic,
        "ic_ir": float(ic_ir) if np.isfinite(ic_ir) else np.nan,
        "ic_positive_ratio": float((series > 0).mean()),
        "ic_negative_ratio": float((series < 0).mean()),
        "ic_abs_mean": float(series.abs().mean()),
        "ic_count": int(len(series)),
    }


def summarize_rank_ic(
    rank_ic_series_v392: pd.Series,
    ddof: int = 1,
) -> Dict[str, float]:
    series = pd.to_numeric(
        rank_ic_series_v392,
        errors="coerce",
    ).dropna()
    if series.empty:
        return {
            "rank_ic_mean": np.nan,
            "rank_ic_std": np.nan,
            "rank_ic_ir": np.nan,
            "rank_ic_positive_ratio": np.nan,
            "rank_ic_negative_ratio": np.nan,
            "rank_ic_abs_mean": np.nan,
            "rank_ic_count": 0,
        }
    mean_ic = float(series.mean())
    std_ic = float(series.std(ddof=ddof))
    if std_ic > 0 and np.isfinite(std_ic):
        ic_ir = mean_ic / std_ic
    else:
        ic_ir = np.nan
    return {
        "rank_ic_mean": mean_ic,
        "rank_ic_std": std_ic,
        "rank_ic_ir": float(ic_ir) if np.isfinite(ic_ir) else np.nan,
        "rank_ic_positive_ratio": float((series > 0).mean()),
        "rank_ic_negative_ratio": float((series < 0).mean()),
        "rank_ic_abs_mean": float(series.abs().mean()),
        "rank_ic_count": int(len(series)),
    }
            # ============================================================
            # Quantile Assignment
            # ============================================================


def assign_quantiles(
    signal: pd.Series,
    quantiles: int = 5,
) -> pd.Series:
    """
    对单个横截面信号进行分组。
    返回：
    1
    =
    最低信号组
    quantiles
    =
    最高信号组
    使用 rank
    (
    method
    =
    'first'
    )
    避免 qcut
    因大量重复值导致分组失败。
    """
    if quantiles < 2:
        raise ValueError("quantiles 必须 >= 2")
    result = pd.Series(
        np.nan,
        index=signal.index,
        dtype=float,
    )
    valid = signal.notna() & np.isfinite(signal)
    if valid.sum() == 0:
        return result
    values = signal.loc[valid]
    if values.nunique() == 1:
        result.loc[valid] = 1
        return result
    ranks = values.rank(method="first")
    n = len(ranks)
    # percentile -> quantile
    groups = np.ceil(ranks / n * quantiles)
    groups = groups.clip(
        lower=1,
        upper=quantiles,
    )
    result.loc[valid] = groups
    return result
                # ============================================================
                # Quantile Portfolio Returns
                # ============================================================


def compute_quantile_returns(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> pd.DataFrame:
    config = config or AlphaMetricsConfigV392()
    df = _prepare_data(
        data,
        config,
    )
    records = []
    for date, group in df.groupby(
        config.date_column,
        sort=True,
    ):
        signal = group[config.signal_column]
        target = group[config.forward_return_column]
        valid = (
            signal.notna() & target.notna() & np.isfinite(signal) & np.isfinite(target)
        )
        if valid.sum() < config.min_obs:
            continue
        sub = group.loc[valid].copy()
        sub["_quantile"] = assign_quantiles(
            sub[config.signal_column],
            config.quantiles,
        )
        row = {config.date_column: date}
        for q in range(
            1,
            config.quantiles + 1,
        ):
            values = sub.loc[
                sub["_quantile"] == q,
                config.forward_return_column,
            ]
            if len(values) == 0:
                row[f"Q {q} "] = np.nan
            else:
                row[f"Q {q} "] = float(values.mean())
        low = row.get("Q 1 ", np.nan)
        high = row.get(
            f"Q {config .quantiles} ",
            np.nan,
        )
        row["High_Low_Spread"] = (
            high - low if np.isfinite(high) and np.isfinite(low) else np.nan
        )
        records.append(row)
    if not records:
        columns = [
            f"Q {q} "
            for q in range(
                1,
                config.quantiles + 1,
            )
        ]
        columns.append("High_Low_Spread")
        return pd.DataFrame(columns=columns)
    result = pd.DataFrame(records).set_index(config.date_column)
    return result
                        # ============================================================
                        # Quantile Summary
                        # ============================================================


def summarize_quantiles(
    quantile_returns: pd.DataFrame,
    quantiles: int = 5,
) -> Dict[str, float]:
    result = {}
    for q in range(
        1,
        quantiles + 1,
    ):
        column = f"Q {q} "
        if column not in quantile_returns.columns:
            result[f" {column} _mean"] = np.nan
            continue
        series = pd.to_numeric(
            quantile_returns[column],
            errors="coerce",
        ).dropna()
        result[f" {column} _mean"] = (
            float(series.mean()) if not series.empty else np.nan
        )
        spread = pd.to_numeric(
            quantile_returns.get(
                "High_Low_Spread",
                pd.Series(dtype=float),
            ),
            errors="coerce",
        ).dropna()
        if spread.empty:
            result["high_low_mean"] = np.nan
            result["high_low_std"] = np.nan
            result["high_low_ir"] = np.nan
            result["high_low_positive_ratio"] = np.nan
        else:
            spread_mean = float(spread.mean())
            spread_std = float(spread.std(ddof=1))
            result["high_low_mean"] = spread_mean
            result["high_low_std"] = spread_std
            result["high_low_ir"] = (
                spread_mean / spread_std if spread_std > 0 else np.nan
            )
        result["high_low_positive_ratio"] = float((spread > 0).mean())
        return result
                # ============================================================
                # Portfolio Weights
                # ============================================================


def _long_only_weights(
    group: pd.DataFrame,
    config: AlphaMetricsConfigV392,
) -> pd.Series:
    signal = group[config.signal_column]
    target_q = assign_quantiles(
        signal,
        config.quantiles,
    )
    selected = target_q == config.long_quantile
    weights = pd.Series(
        0.0,
        index=group.index,
    )
    count = int(selected.sum())
    if count > 0:
        weights.loc[selected] = 1.0 / count
        return weights


def _long_short_weights(
    group: pd.DataFrame,
    config: AlphaMetricsConfigV392,
) -> pd.Series:
    signal = group[config.signal_column]
    q = assign_quantiles(
        signal,
        config.quantiles,
    )
    weights = pd.Series(
        0.0,
        index=group.index,
    )
    long_mask = q == config.quantiles
    short_mask = q == 1
    n_long = int(long_mask.sum())
    n_short = int(short_mask.sum())
    if n_long > 0:
        weights.loc[long_mask] = 0.5 / n_long
        if n_short > 0:
            weights.loc[short_mask] = -0.5 / n_short
            return weights
            # ============================================================
            # Turnover
            # ============================================================


def compute_turnover(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
    portfolio: str = "long_only",
) -> pd.Series:
    config = config or AlphaMetricsConfigV392()
    if portfolio not in {
        "long_only",
        "long_short",
    }:
        raise ValueError("portfolio 必须是 " "'long_only' 或 'long_short'")
    df = _prepare_data(
        data,
        config,
    )
    previous_weights = pd.Series(dtype=float)
    turnover_records = []
    for date, group in df.groupby(
        config.date_column,
        sort=True,
    ):
        if portfolio == "long_only":
            weights = _long_only_weights(
                group,
                config,
            )
        else:
            weights = _long_short_weights(
                group,
                config,
            )
            current = pd.Series(
                weights.to_numpy(),
                index=group[config.code_column].astype(str).to_numpy(),
            )
            if previous_weights.empty:
                turnover = np.nan
            else:
                all_codes = previous_weights.index.union(current.index)
                previous_aligned = previous_weights.reindex(
                    all_codes,
                    fill_value=0.0,
                )
                current_aligned = current.reindex(
                    all_codes,
                    fill_value=0.0,
                )
                turnover = 0.5 * (current_aligned - previous_aligned).abs().sum()
                turnover_records.append((date, turnover))
                previous_weights = current
        result = pd.Series(
            data=[value for _, value in turnover_records],
            index=[date for date, _ in turnover_records],
            name="turnover",
            dtype=float,
        )
        result.index.name = config.date_column
        return result
                    # ============================================================
                    # Signal Autocorrelation
                    # ============================================================


def compute_signal_autocorrelation(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> float:
    config = config or AlphaMetricsConfigV392()
    df = _prepare_data(
        data,
        config,
    )
    signal = config.signal_column
    code = config.code_column
    date = config.date_column
    df = df.sort_values([code, date]).copy()
    df["_signal_lag1"] = df.groupby(code)[signal].shift(1)
    return _safe_corr(
        df[signal],
        df["_signal_lag1"],
    )
    # ============================================================
    # Time Series Performance Metrics
    # ============================================================


def compute_performance_metrics(
    returns: pd.Series,
    annualization: int = 252,
) -> Dict[str, float]:
    """
    对每日收益序列计算：

    -
    mean return

    -
    volatility

    -
    annualized return

    -
    Sharpe

    -
    max drawdown

    -
    win rate
    """
    series = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()
    if series.empty:
        return {
            "mean_return": np.nan,
            "volatility": np.nan,
            "annualized_return": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "win_rate": np.nan,
            "return_count": 0,
        }
        mean_return = float(series.mean())
        volatility = float(series.std(ddof=1))
        cumulative = (1.0 + series).cumprod()
        running_max = cumulative.cummax()
        drawdown = cumulative / running_max - 1.0
        max_drawdown = float(drawdown.min())
        # 几何年化收益
        total_return = cumulative.iloc[-1]
        n_periods = len(series)
        if total_return > 0:
            annualized_return = total_return ** (annualization / n_periods) - 1.0
        else:
            annualized_return = -1.0
            if volatility > 0 and np.isfinite(volatility):
                sharpe = mean_return / volatility * np.sqrt(annualization)
            else:
                sharpe = np.nan
                win_rate = float((series > 0).mean())
                return {
                    "mean_return": mean_return,
                    "volatility": volatility,
                    "annualized_return": float(annualized_return),
                    "sharpe": float(sharpe) if np.isfinite(sharpe) else np.nan,
                    "max_drawdown": max_drawdown,
                    "win_rate": win_rate,
                    "return_count": int(n_periods),
                }
                # ============================================================
                # Alpha Metric Engine
                # ============================================================


class AlphaMetricsEngineV392:
    """
    Alpha Metrics 主引擎。
    """

    def __init__(
        self,
        config: Optional[AlphaMetricsConfigV392] = None,
    ):
        self.config = config or AlphaMetricsConfigV392()
        # --------------------------------------------------------
        # IC
        # --------------------------------------------------------

    def ic_series_v392(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        return compute_ic_series(
            data,
            self.config,
        )
        # --------------------------------------------------------
        # Rank IC
        # --------------------------------------------------------

    def rank_ic_series_v392(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        return compute_rank_ic_series(
            data,
            self.config,
        )
        # --------------------------------------------------------
        # Quantile
        # --------------------------------------------------------

    def quantile_returns(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        return compute_quantile_returns(
            data,
            self.config,
        )
        # --------------------------------------------------------
        # Turnover
        # --------------------------------------------------------

    def turnover(
        self,
        data: pd.DataFrame,
        portfolio: str = "long_only",
    ) -> pd.Series:
        return compute_turnover(
            data,
            self.config,
            portfolio=portfolio,
        )
        # --------------------------------------------------------
        # Signal Stability
        # --------------------------------------------------------

    def signal_autocorrelation(
        self,
        data: pd.DataFrame,
    ) -> float:
        return compute_signal_autocorrelation(
            data,
            self.config,
        )
        # --------------------------------------------------------
        # Full metrics
        # --------------------------------------------------------

    def compute(
        self,
        data: pd.DataFrame,
    ) -> AlphaMetricsResultV392:
        df = _prepare_data(
            data,
            self.config,
        )
        ic = self.ic_series_v392(df)
        rank_ic = self.rank_ic_series_v392(df)
        quantile_returns = self.quantile_returns(df)
        turnover = self.turnover(
            df,
            portfolio="long_only",
        )
        signal_ac = self.signal_autocorrelation(df)
        summary = {}
        # IC
        summary.update(
            summarize_ic(
                ic,
                ddof=self.config.ic_std_ddof,
            )
        )
        # Rank IC
        summary.update(
            summarize_rank_ic(
                rank_ic,
                ddof=self.config.ic_std_ddof,
            )
        )
        # Quantile
        summary.update(
            summarize_quantiles(
                quantile_returns,
                quantiles=self.config.quantiles,
            )
        )
        # Turnover
        turnover_valid = turnover.dropna()
        if turnover_valid.empty:
            summary["turnover_mean"] = np.nan
            summary["turnover_median"] = np.nan
        else:
            summary["turnover_mean"] = float(turnover_valid.mean())
            summary["turnover_median"] = float(turnover_valid.median())
        summary["signal_autocorrelation"] = signal_ac
        diagnostics = {
            "rows": int(len(df)),
            "dates": int(df[self.config.date_column].nunique()),
            "stocks": int(df[self.config.code_column].nunique()),
            "quantiles": self.config.quantiles,
            "min_obs": self.config.min_obs,
        }
        return AlphaMetricsResultV392(
            summary=summary,
            ic_series_v392=ic,
            rank_ic_series_v392=rank_ic,
            quantile_returns=quantile_returns,
            turnover_series=turnover,
            signal_autocorrelation=signal_ac,
            diagnostics=diagnostics,
        )
            # ============================================================
            # Convenience Functions
            # ============================================================


def alpha_metrics_v392(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> AlphaMetricsResultV392:
    engine = AlphaMetricsEngineV392(config=config)
    return engine.compute(data)


def ic_series_v392(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> pd.Series:
    return compute_ic_series(
        data,
        config=config,
    )


def rank_ic_series_v392(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> pd.Series:
    return compute_rank_ic_series(
        data,
        config=config,
    )


def quantile_analysis_v392(
    data: pd.DataFrame,
    config: Optional[AlphaMetricsConfigV392] = None,
) -> pd.DataFrame:
    return compute_quantile_returns(
        data,
        config=config,
    )
    # ============================================================
    # Self Test
    # ============================================================


def _self_test():
    print("Running alpha.metrics self-test...")
    rng = np.random.default_rng(42)
    dates = pd.date_range(
        "2024-01-01",
        periods=80,
        freq="B",
    )
    codes = [f" {i: 06d} " for i in range(1, 101)]
    records = []
    for date in dates:
        base_signal = rng.normal(
            0,
            1,
            len(codes),
        )
        noise = rng.normal(
            0,
            0.5,
            len(codes),
        )
        # 构造一个明显正向的隐藏 Alpha
        forward_return = 0.03 * base_signal + noise * 0.01
        for code, signal, ret in zip(
            codes,
            base_signal,
            forward_return,
        ):
            records.append(
                {
                    "date": date,
                    "code": code,
                    "signal": signal,
                    "forward_return": ret,
                }
            )
    df = pd.DataFrame(records)
    config = AlphaMetricsConfigV392(
        quantiles=5,
        min_obs=30,
    )
    engine = AlphaMetricsEngineV392(config)
    result = engine.compute(df)
    # --------------------------------------------------------
    # Basic checks
    # --------------------------------------------------------
    assert not result.ic_series_v392.empty
    assert not (result.rank_ic_series_v392.empty)
    assert not (result.quantile_returns.empty)
    assert result.summary["ic_mean"] > 0
    assert result.summary["rank_ic_mean"] > 0
    assert result.summary["high_low_mean"] > 0
    # turnover should be within reasonable range
    turnover = result.turnover_series.dropna()
    assert turnover.empty or (turnover >= 0).all()
    # signal autocorrelation should be finite
    # because this synthetic alpha is independent
    # it should be relatively close to zero
    assert np.isfinite(result.signal_autocorrelation)
    print(" \n == =  IC Summary  == = ")
    print(result.summary_frame().to_string(index=False))
    print(" \n == =  Quantile Returns  == = ")
    print(result.quantile_returns.head().to_string())
    print(" \n == =  Diagnostics  == = ")
    print(result.diagnostics)
    print(" \n alpha .metrics self - test PASSED .")
            # ============================================================
            # CLI
            # ============================================================
if __name__ == "__main__":
    _self_test()
