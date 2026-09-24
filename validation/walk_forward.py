"""V3.9.1 walk-forward rolling splits."""
from __future__ import annotations


def rolling_splits(
    dates,
    train: int = 252,
    val: int = 63,
    test: int = 63,
    step: int = 63,
):
    """按时间顺序滚动切分 (train_idx, val_idx, test_idx)。"""
    n = len(dates)
    splits = []
    start = 0
    while start + train + val + test <= n:
        train_idx = list(range(start, start + train))
        val_idx = list(range(start + train, start + train + val))
        test_idx = list(range(start + train + val, start + train + val + test))
        splits.append((train_idx, val_idx, test_idx))
        start += step
    return splits


# ============================================================================
# V3.9.2 WalkForwardValidator (Alpha Research Engine)
# ============================================================================
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 504; validation_days: int = 126; test_days: int = 126
    step_days: int = 63; purge_days: int = 5; embargo_days: int = 5; min_windows: int = 3


@dataclass
class WalkForwardWindow:
    window_id: int; train: pd.DataFrame; validation: pd.DataFrame; test: pd.DataFrame
    purged: pd.DataFrame; embargo: pd.DataFrame; metadata: dict = field(default_factory=dict)


@dataclass
class WalkForwardResult:
    alpha: Any; windows: list; passed: bool; summary: dict


def _wf_eval(a, df):
    y = a(df) if callable(a) else a.evaluate(df) if hasattr(a, "evaluate") else df[a]
    if isinstance(y, pd.DataFrame):
        y = y.iloc[:, 0]
    return pd.Series(y, index=df.index, dtype=float)


def _ic(s, t):
    z = pd.concat([s, t], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    return np.nan if len(z) < 3 else float(z.iloc[:, 0].rank().corr(z.iloc[:, 1].rank()))


def calculate_turnover(previous_holdings, current_holdings):
    if not previous_holdings and not current_holdings:
        return 0.
    return len(set(previous_holdings) ^ set(current_holdings)) / max(len(set(previous_holdings) | set(current_holdings)), 1)


def calculate_quantile_spread(df, signal_col="signal", target_col="forward_return", q=5):
    vals = []
    for _, d in df.groupby("date"):
        z = d[[signal_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(z) < q * 2:
            continue
        try:
            lab = pd.qcut(z[signal_col].rank(method="first"), q=q, labels=False)
        except ValueError:
            continue
        z = z.assign(_q=lab)
        vals.append(float(z.loc[z._q == q - 1, target_col].mean() - z.loc[z._q == 0, target_col].mean()))
    return float(np.mean(vals)) if vals else np.nan


class WalkForwardValidator:
    def __init__(self, train_days=504, validation_days=126, test_days=126, step_days=63,
                 purge_days=5, embargo_days=5, min_windows=3, config=None):
        self.config = config or WalkForwardConfig(train_days, validation_days, test_days, step_days,
                                                 purge_days, embargo_days, min_windows)

    def build_windows(self, panel):
        x = panel.copy(); x.date = pd.to_datetime(x.date); x.code = x.code.astype(str)
        x = x.sort_values(["date", "code"])
        dates = pd.Index(sorted(x.date.unique())); c = self.config
        need = c.train_days + c.purge_days + c.validation_days + c.embargo_days + c.test_days
        out = []; start = 0; wid = 0
        while start + need <= len(dates):
            a = start; b = a + c.train_days; p = b + c.purge_days; v = p + c.validation_days
            e = v + c.embargo_days; t = e + c.test_days
            take = lambda ds: x[x.date.isin(ds)].copy()
            tr, pu, va, em, te = map(take, [dates[a:b], dates[b:p], dates[p:v], dates[v:e], dates[e:t]])
            out.append(WalkForwardWindow(wid, tr, va, te, pu, em, {
                "train_start": str(dates[a]), "train_end": str(dates[b - 1]),
                "test_start": str(dates[e]), "test_end": str(dates[t - 1])}))
            wid += 1; start += c.step_days
        return out

    def validate(self, alpha, panel, target_col="forward_return_5d"):
        x = panel.copy()
        if target_col not in x:
            from backtest.returns import calculate_forward_returns
            x[target_col] = calculate_forward_returns(x, 5, "next_open").to_numpy()
        rows = []
        for w in self.build_windows(x):
            for stage, df in [("train", w.train), ("validation", w.validation), ("test", w.test)]:
                z = df.copy(); z["signal"] = _wf_eval(alpha, z).to_numpy(); ics = []
                for _, d in z.groupby("date"):
                    q = _ic(d.signal, d[target_col])
                    if pd.notna(q):
                        ics.append(q)
                spread = calculate_quantile_spread(z, "signal", target_col)
                sd = np.std(ics, ddof=1) if len(ics) > 1 else np.nan
                rows.append({"window_id": w.window_id, "stage": stage,
                             "ic": np.mean(ics) if ics else np.nan,
                             "icir": np.mean(ics) / sd if len(ics) > 1 and sd > 0 else np.nan,
                             "quantile_spread": spread, "n_days": len(ics)})
        m = pd.DataFrame(rows); test = m[m.stage == "test"]
        passed = (len(test) >= self.config.min_windows
                  and test.ic.notna().sum() >= self.config.min_windows
                  and test.ic.mean() >= .02
                  and test.icir.dropna().mean() >= .20
                  and test.quantile_spread.dropna().mean() >= .003)
        windows = self.build_windows(x)
        return WalkForwardResult(alpha, windows, bool(passed), {
            "n_windows": len(windows), "n_test_windows": len(test),
            "mean_test_ic": float(test.ic.mean()) if len(test) else np.nan,
            "mean_test_icir": float(test.icir.mean()) if len(test) else np.nan,
            "mean_test_quantile_spread": float(test.quantile_spread.mean()) if len(test) else np.nan,
            "passed": bool(passed), "metrics": m.to_dict("records")})

    def run_with_callback(self, panel, callback):
        return [callback(w) for w in self.build_windows(panel)]


def evaluate_alpha_oos(alpha, panel, min_ic=.02, min_train_retention=.30, target_col="forward_return_5d"):
    x = panel.copy(); x.date = pd.to_datetime(x.date)
    if target_col not in x:
        from backtest.returns import calculate_forward_returns
        x[target_col] = calculate_forward_returns(x, 5, "next_open").to_numpy()
    dates = pd.Index(sorted(x.date.unique())); n = len(dates)
    tr = int(n * .6); te = int(n * .8)

    def ev(df):
        z = df.copy(); z["signal"] = _wf_eval(alpha, z)
        vals = [_ic(d.signal, d[target_col]) for _, d in z.groupby("date")]
        vals = [v for v in vals if pd.notna(v)]
        return np.mean(vals) if vals else np.nan

    train_ic = ev(x[x.date.isin(dates[:tr])]); oos_ic = ev(x[x.date.isin(dates[te:])])
    passed = pd.notna(oos_ic) and abs(oos_ic) >= min_ic and (pd.isna(train_ic) or abs(oos_ic) >= min_train_retention * abs(train_ic))
    return type("OOSResult", (), {"alpha": alpha, "train_ic": train_ic,
                                  "oos_ic": oos_ic, "passed": bool(passed)})()


# ============================================================================
# V3.9.2 Walk Forward Validator - standard walk-forward validation engine
# ============================================================================

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from validation.split import (
    DataSplitV392,
    SplitAuditResultV392,
    SplitConfigV392,
    SplitTypeV392,
    TemporalDataSplitterV392,
)


class WalkForwardErrorV392(Exception):
    """Walk Forward 基础异常。"""


class WalkForwardConfigErrorV392(WalkForwardErrorV392):
    """Walk Forward 配置异常。"""


class WalkForwardLeakageErrorV392(WalkForwardErrorV392):
    """Walk Forward 数据泄漏。"""


@dataclass
class WalkForwardConfigV392:
    """
    Walk Forward 配置。
    """
    split_config: SplitConfigV392 = field(
        default_factory=SplitConfigV392
    )
    # 最少有效 OOS 窗口
    min_valid_windows: int = 3
    # 是否要求所有窗口 test 都非空
    require_test_data: bool = True
    # 是否严格执行窗口审计
    strict_audit: bool = True
    # IC 最低阈值
    min_ic: float = 0.02
    # ICIR 最低阈值
    min_icir: float = 0.30
    # 最低方向一致率
    min_direction_consistency: float = 0.55
    # 最低有效窗口比例
    min_window_pass_rate: float = 0.50
    # Test 指标是否允许 NaN
    allow_nan_metrics: bool = False

    def __post_init__(self) -> None:
        if self.min_valid_windows <= 0:
            raise WalkForwardConfigErrorV392(
                "min_valid_windows 必须 > 0"
            )
        if self.min_ic < 0:
            raise WalkForwardConfigErrorV392(
                "min_ic 不能 < 0"
            )
        if self.min_icir < 0:
            raise WalkForwardConfigErrorV392(
                "min_icir 不能 < 0"
            )
        if not (
            0.0
            <= self.min_direction_consistency
            <= 1.0
        ):
            raise WalkForwardConfigErrorV392(
                "min_direction_consistency 必须在 0~1"
            )
        if not (
            0.0
            <= self.min_window_pass_rate
            <= 1.0
        ):
            raise WalkForwardConfigErrorV392(
                "min_window_pass_rate 必须在 0~1"
            )


@dataclass
class WalkForwardWindowResultV392:
    """
    单个 Walk Forward 窗口结果。
    """
    split_id: int
    train_start: Optional[pd.Timestamp]
    train_end: Optional[pd.Timestamp]
    validation_start: Optional[pd.Timestamp]
    validation_end: Optional[pd.Timestamp]
    test_start: Optional[pd.Timestamp]
    test_end: Optional[pd.Timestamp]
    train_rows: int
    validation_rows: int
    test_rows: int
    metrics: Dict[str, float] = field(
        default_factory=dict
    )
    passed: bool = False
    errors: List[str] = field(
        default_factory=list
    )
    warnings: List[str] = field(
        default_factory=list
    )
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "split_id": self.split_id,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "validation_start": (
                self.validation_start
            ),
            "validation_end": (
                self.validation_end
            ),
            "test_start": self.test_start,
            "test_end": self.test_end,
            "train_rows": self.train_rows,
            "validation_rows": (
                self.validation_rows
            ),
            "test_rows": self.test_rows,
            "metrics": self.metrics,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


@dataclass
class WalkForwardResultV392:
    """
    整个 Walk Forward 结果。
    """
    alpha_id: Optional[str] = None
    windows: List[WalkForwardWindowResultV392] = field(
        default_factory=list
    )
    aggregate_metrics: Dict[str, float] = field(
        default_factory=dict
    )
    passed: bool = False
    errors: List[str] = field(
        default_factory=list
    )
    warnings: List[str] = field(
        default_factory=list
    )
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_frame(self) -> pd.DataFrame:
        rows = [
            item.to_dict()
            for item in self.windows
        ]
        if not rows:
            return pd.DataFrame()
        flattened = []
        for row in rows:
            output = {
                key: value
                for key, value in row.items()
                if key != "metrics"
            }
            output.update(
                row.get("metrics", {})
            )
            flattened.append(output)
        return pd.DataFrame(flattened)

    def summary(self) -> Dict[str, Any]:
        return {
            "alpha_id": self.alpha_id,
            "window_count": len(self.windows),
            "passed_windows": sum(
                1 for w in self.windows if w.passed
            ),
            "failed_windows": sum(
                1 for w in self.windows if not w.passed
            ),
            "passed": self.passed,
            "aggregate_metrics": (
                self.aggregate_metrics
            ),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


def _safe_corr_v392(
    x: pd.Series,
    y: pd.Series,
) -> float:
    data = pd.concat(
        [x, y],
        axis=1,
    ).dropna()
    if len(data) < 3:
        return float("nan")
    if (
        data.iloc[:, 0].nunique() <= 1
        or data.iloc[:, 1].nunique() <= 1
    ):
        return float("nan")
    value = data.iloc[:, 0].corr(
        data.iloc[:, 1],
        method="spearman",
    )
    if pd.isna(value):
        return float("nan")
    return float(value)


def _safe_mean_v392(
    values: Iterable[float],
) -> float:
    arr = np.asarray(
        list(values),
        dtype=float,
    )
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.mean(arr))


def _safe_std_v392(
    values: Iterable[float],
) -> float:
    arr = np.asarray(
        list(values),
        dtype=float,
    )
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return float("nan")
    return float(
        np.std(
            arr,
            ddof=1,
        )
    )


def _safe_median_v392(
    values: Iterable[float],
) -> float:
    arr = np.asarray(
        list(values),
        dtype=float,
    )
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.median(arr))


def calculate_ic_v392(
    df: pd.DataFrame,
    signal_column: str,
    return_column: str,
) -> float:
    if (
        signal_column not in df.columns
        or return_column not in df.columns
    ):
        return float("nan")
    return _safe_corr_v392(
        df[signal_column],
        df[return_column],
    )


def calculate_icir_v392(
    ic_values: Sequence[float],
) -> float:
    mean_ic = _safe_mean_v392(ic_values)
    std_ic = _safe_std_v392(ic_values)
    if (
        not np.isfinite(mean_ic)
        or not np.isfinite(std_ic)
        or std_ic == 0
    ):
        return float("nan")
    return float(mean_ic / std_ic)


def calculate_quantile_spread_v392(
    df: pd.DataFrame,
    signal_column: str,
    return_column: str,
    date_column: str = "date",
    quantile: float = 0.20,
) -> float:
    required = {
        signal_column,
        return_column,
        date_column,
    }
    if not required.issubset(df.columns):
        return float("nan")
    if not (0 < quantile < 0.5):
        raise ValueError(
            "quantile 必须在 0~0.5"
        )
    daily_spreads: List[float] = []
    working = df[
        [
            date_column,
            signal_column,
            return_column,
        ]
    ].copy()
    working = working.dropna()
    if working.empty:
        return float("nan")
    for _, group in working.groupby(
        date_column,
        sort=True,
    ):
        if len(group) < 5:
            continue
        lower_threshold = group[
            signal_column
        ].quantile(quantile)
        upper_threshold = group[
            signal_column
        ].quantile(1 - quantile)
        q1 = group.loc[
            group[signal_column]
            <= lower_threshold,
            return_column,
        ]
        q5 = group.loc[
            group[signal_column]
            >= upper_threshold,
            return_column,
        ]
        if q1.empty or q5.empty:
            continue
        spread = (
            q5.mean() - q1.mean()
        )
        daily_spreads.append(
            float(spread)
        )
    return _safe_mean_v392(daily_spreads)


def calculate_turnover_v392(
    df: pd.DataFrame,
    signal_column: str,
    date_column: str = "date",
    quantile: float = 0.20,
) -> float:
    """
    简化横截面 Top/Bottom 换手估计。
    """
    required = {
        signal_column,
        date_column,
    }
    if not required.issubset(df.columns):
        return float("nan")
    working = df[
        [
            date_column,
            signal_column,
        ]
    ].copy()
    working = working.dropna()
    if working.empty:
        return float("nan")
    selected_sets: List[set] = []
    for date, group in working.groupby(
        date_column,
        sort=True,
    ):
        if len(group) < 5:
            continue
        group = group.copy()
        threshold = group[
            signal_column
        ].quantile(1 - quantile)
        selected = set(
            group.index[
                group[signal_column]
                >= threshold
            ]
        )
        selected_sets.append(selected)
    if len(selected_sets) < 2:
        return float("nan")
    turnovers = []
    for previous, current in zip(
        selected_sets[:-1],
        selected_sets[1:],
    ):
        if not current:
            continue
        overlap = len(previous & current)
        turnover = (
            1.0
            - overlap
            / max(len(current), 1)
        )
        turnovers.append(turnover)
    return _safe_mean_v392(turnovers)


class WalkForwardMetricsV392:
    def __init__(
        self,
        date_column: str = "date",
    ) -> None:
        self.date_column = date_column

    def calculate(
        self,
        df: pd.DataFrame,
        signal_column: str,
        return_column: str,
    ) -> Dict[str, float]:
        metrics: Dict[str, float] = {}
        # ----------------------------------------------------
        # Overall IC
        # ----------------------------------------------------
        metrics["ic"] = calculate_ic_v392(
            df,
            signal_column,
            return_column,
        )
        # ----------------------------------------------------
        # Daily IC
        # ----------------------------------------------------
        daily_ic: List[float] = []
        if self.date_column in df.columns:
            for _, group in df.groupby(
                self.date_column,
                sort=True,
            ):
                ic = calculate_ic_v392(
                    group,
                    signal_column,
                    return_column,
                )
                if np.isfinite(ic):
                    daily_ic.append(ic)
        metrics["ic_mean"] = _safe_mean_v392(
            daily_ic
        )
        metrics["ic_std"] = _safe_std_v392(
            daily_ic
        )
        metrics["ic_median"] = _safe_median_v392(
            daily_ic
        )
        metrics["icir"] = calculate_icir_v392(
            daily_ic
        )
        # ----------------------------------------------------
        # IC positive ratio
        # ----------------------------------------------------
        if daily_ic:
            metrics["ic_positive_ratio"] = float(
                np.mean(
                    np.asarray(daily_ic) > 0
                )
            )
            metrics["ic_negative_ratio"] = float(
                np.mean(
                    np.asarray(daily_ic) < 0
                )
            )
        else:
            metrics["ic_positive_ratio"] = float(
                "nan"
            )
            metrics["ic_negative_ratio"] = float(
                "nan"
            )
        # ----------------------------------------------------
        # Q5-Q1
        # ----------------------------------------------------
        metrics["q5_q1"] = calculate_quantile_spread_v392(
            df,
            signal_column,
            return_column,
            date_column=self.date_column,
        )
        # ----------------------------------------------------
        # Turnover
        # ----------------------------------------------------
        metrics["turnover"] = calculate_turnover_v392(
            df,
            signal_column,
            date_column=self.date_column,
        )
        return metrics


class WalkForwardValidatorV392:
    """
    标准 Walk Forward Validator。
    """

    def __init__(
        self,
        config: Optional[
            WalkForwardConfigV392
        ] = None,
    ) -> None:
        self.config = (
            config or WalkForwardConfigV392()
        )
        self.splitter = (
            TemporalDataSplitterV392(
                self.config.split_config
            )
        )
        self.metrics = (
            WalkForwardMetricsV392(
                date_column=(
                    self.config.split_config.date_column
                )
            )
        )

    # --------------------------------------------------------
    # Build splits
    # --------------------------------------------------------
    def build_splits(
        self,
        df: pd.DataFrame,
    ) -> List[DataSplitV392]:
        splits = (
            self.splitter.split_all(df)
        )
        audit = (
            self.splitter.audit_all(splits)
        )
        if (
            self.config.strict_audit
            and not audit.passed
        ):
            raise WalkForwardLeakageErrorV392(
                audit.summary()
                + "\n"
                + "\n".join(audit.errors)
            )
        return splits

    # --------------------------------------------------------
    # Validate one window
    # --------------------------------------------------------
    def evaluate_window(
        self,
        split: DataSplitV392,
        signal_column: str,
        return_column: str,
    ) -> WalkForwardWindowResultV392:
        test = split.test
        errors: List[str] = []
        warnings: List[str] = []
        if test.empty:
            if (
                self.config.require_test_data
            ):
                errors.append(
                    "Test 数据为空。"
                )
            metrics = {}
        else:
            metrics = (
                self.metrics.calculate(
                    test,
                    signal_column,
                    return_column,
                )
            )
        # ----------------------------------------------------
        # Metric validation
        # ----------------------------------------------------
        for name, value in metrics.items():
            if not np.isfinite(value):
                if (
                    not self.config.allow_nan_metrics
                ):
                    warnings.append(
                        f"指标 {name} = NaN"
                    )
        # ----------------------------------------------------
        # Window pass
        # ----------------------------------------------------
        ic = metrics.get(
            "ic_mean",
            np.nan,
        )
        icir = metrics.get(
            "icir",
            np.nan,
        )
        positive_ratio = metrics.get(
            "ic_positive_ratio",
            np.nan,
        )
        passed = True
        if (
            np.isfinite(ic)
            and abs(ic)
            < self.config.min_ic
        ):
            passed = False
            warnings.append(
                "IC 未达到最低阈值。"
            )
        if (
            np.isfinite(icir)
            and abs(icir)
            < self.config.min_icir
        ):
            passed = False
            warnings.append(
                "ICIR 未达到最低阈值。"
            )
        if (
            np.isfinite(positive_ratio)
            and positive_ratio
            < self.config.min_direction_consistency
        ):
            passed = False
            warnings.append(
                "IC 正方向一致率不足。"
            )
        if errors:
            passed = False
        return WalkForwardWindowResultV392(
            split_id=split.window.split_id,
            train_start=(
                split.window.train_start
            ),
            train_end=(
                split.window.train_end
            ),
            validation_start=(
                split.window.validation_start
            ),
            validation_end=(
                split.window.validation_end
            ),
            test_start=(
                split.window.test_start
            ),
            test_end=(
                split.window.test_end
            ),
            train_rows=len(split.train),
            validation_rows=len(
                split.validation
            ),
            test_rows=len(split.test),
            metrics=metrics,
            passed=passed,
            errors=errors,
            warnings=warnings,
            metadata={
                "split_type": (
                    split.window.split_type.value
                ),
            },
        )

    # --------------------------------------------------------
    # Aggregate windows
    # --------------------------------------------------------
    def aggregate(
        self,
        windows: Sequence[
            WalkForwardWindowResultV392
        ],
    ) -> Dict[str, float]:
        if not windows:
            return {}
        metric_names = set()
        for window in windows:
            metric_names.update(
                window.metrics.keys()
            )
        aggregate: Dict[str, float] = {}
        # ----------------------------------------------------
        # Basic statistics
        # ----------------------------------------------------
        for name in sorted(metric_names):
            values = [
                w.metrics[name]
                for w in windows
                if name in w.metrics
            ]
            aggregate[
                f"{name}_mean"
            ] = _safe_mean_v392(values)
            aggregate[
                f"{name}_median"
            ] = _safe_median_v392(values)
            aggregate[
                f"{name}_std"
            ] = _safe_std_v392(values)
        # ----------------------------------------------------
        # Window pass rate
        # ----------------------------------------------------
        pass_values = [
            1.0 if w.passed else 0.0
            for w in windows
        ]
        aggregate[
            "window_pass_rate"
        ] = _safe_mean_v392(pass_values)
        # ----------------------------------------------------
        # Positive IC window ratio
        # ----------------------------------------------------
        ic_values = [
            w.metrics.get(
                "ic_mean",
                np.nan,
            )
            for w in windows
        ]
        ic_values = [
            value
            for value in ic_values
            if np.isfinite(value)
        ]
        if ic_values:
            aggregate[
                "positive_ic_window_ratio"
            ] = float(
                np.mean(
                    np.asarray(ic_values) > 0
                )
            )
            aggregate[
                "negative_ic_window_ratio"
            ] = float(
                np.mean(
                    np.asarray(ic_values) < 0
                )
            )
        else:
            aggregate[
                "positive_ic_window_ratio"
            ] = float("nan")
            aggregate[
                "negative_ic_window_ratio"
            ] = float("nan")
        # ----------------------------------------------------
        # IC decay
        # ----------------------------------------------------
        if len(ic_values) >= 2:
            half = max(
                1,
                len(ic_values) // 2,
            )
            first_half = ic_values[:half]
            second_half = ic_values[half:]
            aggregate[
                "ic_first_half"
            ] = _safe_mean_v392(first_half)
            aggregate[
                "ic_second_half"
            ] = _safe_mean_v392(second_half)
            aggregate[
                "ic_decay"
            ] = (
                aggregate["ic_second_half"]
                - aggregate["ic_first_half"]
            )
        else:
            aggregate["ic_first_half"] = float(
                "nan"
            )
            aggregate["ic_second_half"] = float(
                "nan"
            )
            aggregate["ic_decay"] = float(
                "nan"
            )
        return aggregate

    # --------------------------------------------------------
    # Final decision
    # --------------------------------------------------------
    def evaluate_result(
        self,
        result: WalkForwardResultV392,
    ) -> WalkForwardResultV392:
        windows = result.windows
        if len(windows) < (
            self.config.min_valid_windows
        ):
            result.errors.append(
                "有效 Walk Forward 窗口数量不足。"
                f"required={self.config.min_valid_windows}, "
                f"actual={len(windows)}"
            )
            result.passed = False
            return result
        metrics = result.aggregate_metrics
        # ----------------------------------------------------
        # Average IC
        # ----------------------------------------------------
        avg_ic = metrics.get(
            "ic_mean_mean",
            np.nan,
        )
        if (
            np.isfinite(avg_ic)
            and abs(avg_ic)
            < self.config.min_ic
        ):
            result.errors.append(
                "Walk Forward 平均 IC 未达到阈值。"
            )
        # ----------------------------------------------------
        # Average ICIR
        # ----------------------------------------------------
        avg_icir = metrics.get(
            "icir_mean",
            np.nan,
        )
        if (
            np.isfinite(avg_icir)
            and abs(avg_icir)
            < self.config.min_icir
        ):
            result.errors.append(
                "Walk Forward 平均 ICIR 未达到阈值。"
            )
        # ----------------------------------------------------
        # Direction consistency
        # ----------------------------------------------------
        direction_ratio = metrics.get(
            "positive_ic_window_ratio",
            np.nan,
        )
        if (
            np.isfinite(direction_ratio)
            and direction_ratio
            < self.config.min_direction_consistency
        ):
            result.errors.append(
                "Walk Forward Alpha "
                "方向一致性不足。"
            )
        # ----------------------------------------------------
        # Window pass rate
        # ----------------------------------------------------
        pass_rate = metrics.get(
            "window_pass_rate",
            np.nan,
        )
        if (
            np.isfinite(pass_rate)
            and pass_rate
            < self.config.min_window_pass_rate
        ):
            result.errors.append(
                "Walk Forward 窗口通过率不足。"
            )
        result.passed = (
            len(result.errors) == 0
        )
        return result

    # --------------------------------------------------------
    # Main run
    # --------------------------------------------------------
    def run(
        self,
        df: pd.DataFrame,
        signal_column: str,
        return_column: str,
        alpha_id: Optional[str] = None,
    ) -> WalkForwardResultV392:
        splits = self.build_splits(df)
        window_results = []
        for split in splits:
            window_result = (
                self.evaluate_window(
                    split,
                    signal_column,
                    return_column,
                )
            )
            window_results.append(
                window_result
            )
        aggregate_metrics = (
            self.aggregate(window_results)
        )
        result = WalkForwardResultV392(
            alpha_id=alpha_id,
            windows=window_results,
            aggregate_metrics=aggregate_metrics,
            metadata={
                "signal_column": signal_column,
                "return_column": return_column,
                "split_type": (
                    self.config.split_config.split_type.value
                ),
                "window_count": len(
                    window_results
                ),
            },
        )
        return self.evaluate_result(result)

    # --------------------------------------------------------
    # Callback-based run
    # --------------------------------------------------------
    def run_with_callback(
        self,
        df: pd.DataFrame,
        train_callback: Callable[
            [pd.DataFrame],
            Any,
        ],
        validation_callback: Optional[
            Callable[
                [Any, pd.DataFrame],
                Any,
            ]
        ] = None,
        test_callback: Optional[
            Callable[
                [Any, pd.DataFrame],
                pd.DataFrame,
            ]
        ] = None,
        signal_column: str = "alpha",
        return_column: str = "forward_return",
        alpha_id: Optional[str] = None,
    ) -> WalkForwardResultV392:
        """
        真正的 Walk Forward 模式。
        """
        splits = self.build_splits(df)
        window_results = []
        for split in splits:
            # ------------------------------------------------
            # Train
            # ------------------------------------------------
            model = train_callback(
                split.train.copy()
            )
            # ------------------------------------------------
            # Validation
            # ------------------------------------------------
            if (
                validation_callback is not None
                and not split.validation.empty
            ):
                validation_callback(
                    model,
                    split.validation.copy(),
                )
            # ------------------------------------------------
            # Test
            # ------------------------------------------------
            if test_callback is not None:
                test_output = test_callback(
                    model,
                    split.test.copy(),
                )
                if not isinstance(
                    test_output,
                    pd.DataFrame,
                ):
                    raise WalkForwardErrorV392(
                        "test_callback 必须返回 "
                        "pandas.DataFrame"
                    )
                test_df = test_output
            else:
                test_df = (
                    split.test.copy()
                )
            # ------------------------------------------------
            # Evaluate
            # ------------------------------------------------
            evaluation_split = DataSplitV392(
                window=split.window,
                train=split.train,
                validation=split.validation,
                test=test_df,
                purged=split.purged,
                embargo=split.embargo,
                metadata=split.metadata,
            )
            window_result = (
                self.evaluate_window(
                    evaluation_split,
                    signal_column,
                    return_column,
                )
            )
            window_results.append(
                window_result
            )
        aggregate_metrics = (
            self.aggregate(window_results)
        )
        result = WalkForwardResultV392(
            alpha_id=alpha_id,
            windows=window_results,
            aggregate_metrics=aggregate_metrics,
            metadata={
                "mode": "callback",
                "signal_column": signal_column,
                "return_column": return_column,
                "window_count": len(
                    window_results
                ),
            },
        )
        return self.evaluate_result(result)


def walk_forward_validate_v392(
    df: pd.DataFrame,
    signal_column: str,
    return_column: str,
    config: Optional[
        WalkForwardConfigV392
    ] = None,
    alpha_id: Optional[str] = None,
) -> WalkForwardResultV392:
    validator = WalkForwardValidatorV392(
        config
    )
    return validator.run(
        df=df,
        signal_column=signal_column,
        return_column=return_column,
        alpha_id=alpha_id,
    )


def walk_forward_summary_v392(
    result: WalkForwardResultV392,
) -> pd.DataFrame:
    return result.to_frame()


def _build_demo_data_v392(
    periods: int = 180,
    stocks: int = 50,
) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(
        "2024-01-01",
        periods=periods,
    )
    rows = []
    for date in dates:
        for stock_id in range(stocks):
            code = f"{600000 + stock_id:06d}"
            alpha = rng.normal()
            forward_return = (
                alpha * 0.03
                + rng.normal(scale=0.10)
            )
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "alpha": alpha,
                    "forward_return": (
                        forward_return
                    ),
                }
            )
    return pd.DataFrame(rows)


def self_test_v392() -> None:
    """
    模块自检。
    """
    df = _build_demo_data_v392()
    split_config = SplitConfigV392(
        split_type=SplitTypeV392.EXPANDING,
        min_train_periods=60,
        validation_periods=20,
        test_periods=20,
        step_periods=20,
        purge_periods=2,
        embargo_periods=2,
        require_unique_date_code=True,
    )
    config = WalkForwardConfigV392(
        split_config=split_config,
        min_valid_windows=2,
        min_ic=0.0,
        min_icir=0.0,
        min_direction_consistency=0.0,
        min_window_pass_rate=0.0,
        strict_audit=True,
    )
    validator = (
        WalkForwardValidatorV392(config)
    )
    result = validator.run(
        df,
        signal_column="alpha",
        return_column="forward_return",
        alpha_id="DEMO_ALPHA",
    )
    assert len(result.windows) >= 2
    assert (
        "ic_mean_mean"
        in result.aggregate_metrics
    )
    frame = result.to_frame()
    assert not frame.empty
    # --------------------------------------------------------
    # 验证窗口时间顺序
    # --------------------------------------------------------
    previous_test_end = None
    for window in result.windows:
        if previous_test_end is not None:
            assert (
                window.test_end
                > previous_test_end
            )
        previous_test_end = (
            window.test_end
        )
    # --------------------------------------------------------
    # Callback 模式
    # --------------------------------------------------------
    def train_callback(
        train: pd.DataFrame,
    ) -> Dict[str, Any]:
        return {
            "mean_alpha": float(
                train["alpha"].mean()
            )
        }

    def test_callback(
        model: Dict[str, Any],
        test: pd.DataFrame,
    ) -> pd.DataFrame:
        output = test.copy()
        output["alpha"] = (
            output["alpha"]
        )
        return output

    callback_result = (
        validator.run_with_callback(
            df,
            train_callback=train_callback,
            test_callback=test_callback,
            signal_column="alpha",
            return_column="forward_return",
            alpha_id="DEMO_CALLBACK",
        )
    )
    assert len(callback_result.windows) >= 2
    print(
        "validation/walk_forward.py V392 self_test PASSED"
    )
    print(callback_result.summary())


if __name__ == "__main__":
    self_test_v392()
