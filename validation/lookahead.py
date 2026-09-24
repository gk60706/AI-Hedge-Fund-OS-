from __future__ import annotations

import pandas as pd


class LookaheadDetector:
    def detect(
        self,
        df: pd.DataFrame,
        date_column: str = "date",
        available_column: str = "available_date",
    ) -> dict:
        if (
            date_column not in df.columns
            or available_column not in df.columns
        ):
            return {
                "valid": False,
                "error": ("缺少 date 或 " "available_date"),
            }
        work = df.copy()
        work[date_column] = pd.to_datetime(work[date_column])
        work[available_column] = pd.to_datetime(work[available_column])
        violations = (
            work[work[available_column] > work[date_column]]
        )
        return {
            "valid": violations.empty,
            "violations": len(violations),
        }



# ============================================================================
# V3.9.1 unified research engine - look-ahead detection
# ============================================================================


def find_lookahead(panel: pd.DataFrame) -> list:
    """返回 available_date 晚于 date 的违规行索引（未来数据泄漏）。"""
    violations: list = []
    if panel is None or panel.empty:
        return violations
    if "available_date" not in panel.columns or "date" not in panel.columns:
        return violations
    for idx, row in panel.iterrows():
        if pd.isna(row["available_date"]):
            continue
        if pd.Timestamp(row["available_date"]) > pd.Timestamp(row["date"]):
            violations.append(idx)
    return violations


# ============================================================================
# V3.9.2 - Look-Ahead Bias Detection (appended)
# ============================================================================

# -*- coding: utf-8 -*-
"""
AI Hedge Fund OS
V3.9.2 - Look-Ahead Bias Detection (appended, V392 suffix)

职责：
1. 检测未来函数（Look-Ahead Bias）
2. PIT（Point-in-Time）数据可用性审计
3. Signal / Entry / Exit 时间轴对齐检查
4. Forward Return 构造
5. Rolling window 安全性检查
6. Signal lag 工具
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# Exceptions
# ============================================================
class LookAheadErrorV392(Exception):
    """Look-ahead audit 基础异常。"""


class LookAheadViolationV392(LookAheadErrorV392):
    """检测到明确未来函数。"""


class TemporalAlignmentErrorV392(LookAheadErrorV392):
    """检测到时间轴对齐错误。"""


# ============================================================
# Configuration
# ============================================================
@dataclass
class LookAheadConfigV392:
    """Look-ahead 审计配置。"""
    code_column: str = "code"
    date_column: str = "date"
    available_date_column: str = "available_date"
    signal_date_column: str = "signal_date"
    entry_date_column: str = "entry_date"
    exit_date_column: str = "exit_date"
    forward_return_column: str = "forward_return"
    price_column: str = "close"
    next_open_column: str = "next_open"
    strict: bool = True
    allow_missing_available_date: bool = False
    require_unique_date_code: bool = True
    require_sorted: bool = True
    require_future_return: bool = True
    max_allowed_signal_to_entry_days: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Audit Result
# ============================================================
@dataclass
class LookAheadAuditResultV392:
    passed: bool
    violation_count: int = 0
    warning_count: int = 0
    checked_rows: int = 0
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violation_count": self.violation_count,
            "warning_count": self.warning_count,
            "checked_rows": self.checked_rows,
            "diagnostics": self.diagnostics,
        }

    def to_frame(self) -> pd.DataFrame:
        rows = []
        for item in self.violations:
            rows.append({
                "severity": "violation",
                **item,
            })
        for item in self.warnings:
            rows.append({
                "severity": "warning",
                **item,
            })
        return pd.DataFrame(rows)


# ============================================================
# Helpers
# ============================================================
def _normalize_date_series_v392(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def _is_numeric_series_v392(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def _safe_float_v392(value: Any) -> Optional[float]:
    try:
        value = float(value)
        if not np.isfinite(value):
            return None
        return value
    except (TypeError, ValueError):
        return None


# ============================================================
# Engine
# ============================================================
class LookAheadAuditorV392:
    """
    Look-Ahead Bias 审计器。

    核心时间关系：

        information
             ↓
        available_date
             ↓
        signal_date
             ↓
        entry_date
             ↓
        exit_date
             ↓
        realized_return
    """

    def __init__(
        self,
        config: Optional[LookAheadConfigV392] = None,
    ):
        self.config = (
            config or LookAheadConfigV392()
        )

    # ========================================================
    # Main Audit
    # ========================================================
    def audit(
        self,
        df: pd.DataFrame,
    ) -> LookAheadAuditResultV392:
        if not isinstance(df, pd.DataFrame):
            raise LookAheadErrorV392("Input must be pandas DataFrame.")
        work = df.copy()
        violations: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        diagnostics: Dict[str, Any] = {}

        # ----------------------------------------------------
        # Basic columns
        # ----------------------------------------------------
        self._check_basic_columns(work, violations)
        if violations and self.config.strict:
            return LookAheadAuditResultV392(
                passed=False,
                violation_count=len(violations),
                checked_rows=len(work),
                violations=violations,
                warnings=warnings,
                diagnostics=diagnostics,
            )

        # ----------------------------------------------------
        # Normalize dates
        # ----------------------------------------------------
        date_columns = [
            self.config.date_column,
            self.config.available_date_column,
            self.config.signal_date_column,
            self.config.entry_date_column,
            self.config.exit_date_column,
        ]
        for column in date_columns:
            if column in work.columns:
                work[column] = (
                    _normalize_date_series_v392(work[column])
                )

        # ----------------------------------------------------
        # Duplicate check
        # ----------------------------------------------------
        self._check_duplicates(work, violations, warnings)

        # ----------------------------------------------------
        # Sorting
        # ----------------------------------------------------
        self._check_sorting(work, violations, warnings)

        # ----------------------------------------------------
        # PIT availability
        # ----------------------------------------------------
        self._check_availability(work, violations, warnings)

        # ----------------------------------------------------
        # Signal alignment
        # ----------------------------------------------------
        self._check_signal_alignment(work, violations, warnings)

        # ----------------------------------------------------
        # Entry alignment
        # ----------------------------------------------------
        self._check_entry_alignment(work, violations, warnings)

        # ----------------------------------------------------
        # Exit alignment
        # ----------------------------------------------------
        self._check_exit_alignment(work, violations, warnings)

        # ----------------------------------------------------
        # Forward return
        # ----------------------------------------------------
        self._check_forward_return(work, violations, warnings)

        # ----------------------------------------------------
        # Same-day leakage
        # ----------------------------------------------------
        self._check_same_day_price_usage(work, violations, warnings)

        # ----------------------------------------------------
        # Rolling / shift metadata
        # ----------------------------------------------------
        self._check_temporal_metadata(work, violations, warnings)

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------
        diagnostics["date_min"] = self._date_min(
            work, self.config.date_column,
        )
        diagnostics["date_max"] = self._date_max(
            work, self.config.date_column,
        )
        diagnostics["unique_codes"] = (
            int(work[self.config.code_column].nunique())
            if self.config.code_column in work.columns else None
        )
        diagnostics["available_date_missing"] = (
            int(work[self.config.available_date_column].isna().sum())
            if self.config.available_date_column in work.columns else None
        )

        passed = len(violations) == 0
        return LookAheadAuditResultV392(
            passed=passed,
            violation_count=len(violations),
            warning_count=len(warnings),
            checked_rows=len(work),
            violations=violations,
            warnings=warnings,
            diagnostics=diagnostics,
        )

    # ========================================================
    # Basic Columns
    # ========================================================
    def _check_basic_columns(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
    ) -> None:
        required = [
            self.config.code_column,
            self.config.date_column,
        ]
        if (
            self.config.require_future_return
            and self.config.forward_return_column
        ):
            # forward_return can be absent at raw data stage,
            # therefore it is not treated as hard-required here.
            pass
        for column in required:
            if column not in df.columns:
                violations.append({
                    "type": "missing_column",
                    "column": column,
                    "message": (
                        f"Required column missing: "
                        f"{column}"
                    ),
                })

    # ========================================================
    # Duplicate
    # ========================================================
    def _check_duplicates(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        if not self.config.require_unique_date_code:
            return
        code = self.config.code_column
        date_col = self.config.date_column
        if (
            code not in df.columns
            or date_col not in df.columns
        ):
            return
        duplicate_mask = df.duplicated(
            subset=[code, date_col],
            keep=False,
        )
        count = int(duplicate_mask.sum())
        if count > 0:
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "duplicate_date_code",
                "count": count,
                "message": (
                    "Duplicate code/date rows "
                    "can cause ambiguous temporal "
                    "alignment."
                ),
            })

    # ========================================================
    # Sorting
    # ========================================================
    def _check_sorting(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        if not self.config.require_sorted:
            return
        code = self.config.code_column
        date_col = self.config.date_column
        if (
            code not in df.columns
            or date_col not in df.columns
        ):
            return
        work = df[[code, date_col]].copy()
        sorted_work = work.sort_values(
            [code, date_col]
        ).reset_index(drop=True)
        original_work = work.reset_index(drop=True)
        if not sorted_work.equals(original_work):
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "unsorted_time_series",
                "message": (
                    "Data is not sorted by "
                    "code/date."
                ),
            })

    # ========================================================
    # PIT Availability
    # ========================================================
    def _check_availability(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        available = (
            self.config.available_date_column
        )
        signal = (
            self.config.signal_date_column
        )
        if (
            available not in df.columns
            or signal not in df.columns
        ):
            return
        available_series = df[available]
        signal_series = df[signal]
        missing_mask = (
            available_series.isna()
        )
        if (
            missing_mask.any()
            and not self.config.allow_missing_available_date
        ):
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "missing_available_date",
                "count": int(missing_mask.sum()),
                "message": (
                    "Rows have no information "
                    "availability date."
                ),
            })
        future_mask = (
            available_series > signal_series
        )
        future_mask = (
            future_mask
            & available_series.notna()
            & signal_series.notna()
        )
        if future_mask.any():
            count = int(future_mask.sum())
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "future_available_data",
                "count": count,
                "message": (
                    "available_date is later "
                    "than signal_date."
                ),
            })

    # ========================================================
    # Signal Alignment
    # ========================================================
    def _check_signal_alignment(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        date_col = self.config.date_column
        signal_col = self.config.signal_date_column
        if (
            date_col not in df.columns
            or signal_col not in df.columns
        ):
            return
        date_series = df[date_col]
        signal_series = df[signal_col]
        # Signal date should not be after the
        # observation date when the observation
        # represents the information set.
        invalid_mask = (
            signal_series > date_series
        )
        invalid_mask &= (
            signal_series.notna()
            & date_series.notna()
        )
        if invalid_mask.any():
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "signal_after_observation",
                "count": int(invalid_mask.sum()),
                "message": (
                    "signal_date occurs after "
                    "observation date."
                ),
            })

    # ========================================================
    # Entry Alignment
    # ========================================================
    def _check_entry_alignment(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        signal = self.config.signal_date_column
        entry = self.config.entry_date_column
        if (
            signal not in df.columns
            or entry not in df.columns
        ):
            return
        invalid_mask = (
            df[entry] <= df[signal]
        )
        invalid_mask &= (
            df[entry].notna()
            & df[signal].notna()
        )
        if invalid_mask.any():
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "entry_not_after_signal",
                "count": int(invalid_mask.sum()),
                "message": (
                    "entry_date must be strictly "
                    "after signal_date."
                ),
            })

    # ========================================================
    # Exit Alignment
    # ========================================================
    def _check_exit_alignment(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        entry = self.config.entry_date_column
        exit_col = self.config.exit_date_column
        if (
            entry not in df.columns
            or exit_col not in df.columns
        ):
            return
        invalid_mask = (
            df[exit_col] <= df[entry]
        )
        invalid_mask &= (
            df[exit_col].notna()
            & df[entry].notna()
        )
        if invalid_mask.any():
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "exit_not_after_entry",
                "count": int(invalid_mask.sum()),
                "message": (
                    "exit_date must be after "
                    "entry_date."
                ),
            })

    # ========================================================
    # Forward Return
    # ========================================================
    def _check_forward_return(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        forward_col = (
            self.config.forward_return_column
        )
        entry_col = (
            self.config.entry_date_column
        )
        exit_col = (
            self.config.exit_date_column
        )
        if forward_col not in df.columns:
            return
        if (
            entry_col not in df.columns
            or exit_col not in df.columns
        ):
            return
        # Forward return should represent a period
        # strictly after the signal/entry point.
        invalid_mask = (
            df[exit_col] <= df[entry_col]
        )
        invalid_mask &= (
            df[forward_col].notna()
            & df[entry_col].notna()
            & df[exit_col].notna()
        )
        if invalid_mask.any():
            target = (
                violations if self.config.strict else warnings
            )
            target.append({
                "type": "invalid_forward_return_window",
                "count": int(invalid_mask.sum()),
                "message": (
                    "Forward return contains "
                    "non-forward time window."
                ),
            })

    # ========================================================
    # Same Day Price Usage
    # ========================================================
    def _check_same_day_price_usage(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        """
        检查典型的：

            signal at close T
            trade at close T

        这种隐含未来函数。

        注意：
        这里不能仅凭 DataFrame 自动断定一定错误，
        所以默认生成 warning。

        真正的严格交易规则由 backtest layer 决定。
        """
        date_col = self.config.date_column
        signal_col = self.config.signal_date_column
        entry_col = self.config.entry_date_column
        if (
            date_col not in df.columns
            or signal_col not in df.columns
            or entry_col not in df.columns
        ):
            return
        same_day_mask = (
            df[signal_col] == df[entry_col]
        )
        same_day_mask &= (
            df[signal_col].notna()
            & df[entry_col].notna()
        )
        if same_day_mask.any():
            warnings.append({
                "type": "same_day_signal_entry",
                "count": int(same_day_mask.sum()),
                "message": (
                    "Signal and entry occur on "
                    "the same date. Verify that "
                    "the signal does not use the "
                    "closing price being traded."
                ),
            })

    # ========================================================
    # Temporal Metadata
    # ========================================================
    def _check_temporal_metadata(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        metadata = self.config.metadata
        # ----------------------------------------------------
        # Explicit lookback
        # ----------------------------------------------------
        lookback = metadata.get("lookback")
        if lookback is not None:
            try:
                lookback = int(lookback)
                if lookback < 0:
                    violations.append({
                        "type": "invalid_lookback",
                        "lookback": lookback,
                        "message": (
                            "Lookback cannot be negative."
                        ),
                    })
            except (TypeError, ValueError):
                violations.append({
                    "type": "invalid_lookback",
                    "lookback": lookback,
                    "message": (
                        "Lookback must be integer."
                    ),
                })

        # ----------------------------------------------------
        # Explicit shift
        # ----------------------------------------------------
        shift = metadata.get("shift")
        if shift is not None:
            try:
                shift = int(shift)
                if shift < 0:
                    violations.append({
                        "type": "negative_shift",
                        "shift": shift,
                        "message": (
                            "Negative shift may "
                            "introduce future information."
                        ),
                    })
            except (TypeError, ValueError):
                violations.append({
                    "type": "invalid_shift",
                    "shift": shift,
                    "message": (
                        "Shift must be integer."
                    ),
                })

        # ----------------------------------------------------
        # User explicitly claims no leakage
        # ----------------------------------------------------
        if metadata.get("uses_future_window", False):
            violations.append({
                "type": "future_window_declared",
                "message": (
                    "Metadata declares that "
                    "future window is used."
                ),
            })

    # ========================================================
    # Date helpers
    # ========================================================
    @staticmethod
    def _date_min(
        df: pd.DataFrame,
        column: str,
    ) -> Optional[str]:
        if column not in df.columns:
            return None
        values = pd.to_datetime(
            df[column],
            errors="coerce",
        ).dropna()
        if values.empty:
            return None
        return values.min().date().isoformat()

    @staticmethod
    def _date_max(
        df: pd.DataFrame,
        column: str,
    ) -> Optional[str]:
        if column not in df.columns:
            return None
        values = pd.to_datetime(
            df[column],
            errors="coerce",
        ).dropna()
        if values.empty:
            return None
        return values.max().date().isoformat()


# ============================================================
# Temporal Alignment Utilities
# ============================================================
def validate_signal_entry_dates_v392(
    df: pd.DataFrame,
    signal_date: str = "signal_date",
    entry_date: str = "entry_date",
) -> pd.Series:
    """
    返回 signal -> entry 时间关系是否合法。

    合法条件：

        entry_date > signal_date
    """
    if (
        signal_date not in df.columns
        or entry_date not in df.columns
    ):
        raise LookAheadErrorV392(
            "Missing signal_date or entry_date."
        )
    signal = _normalize_date_series_v392(df[signal_date])
    entry = _normalize_date_series_v392(df[entry_date])
    return (entry > signal)


def validate_available_date_v392(
    df: pd.DataFrame,
    signal_date: str = "signal_date",
    available_date: str = "available_date",
) -> pd.Series:
    """
    返回 PIT 可用性 mask。

    合法：

        available_date <= signal_date
    """
    if (
        signal_date not in df.columns
        or available_date not in df.columns
    ):
        raise LookAheadErrorV392(
            "Missing signal_date or "
            "available_date."
        )
    signal = _normalize_date_series_v392(df[signal_date])
    available = _normalize_date_series_v392(df[available_date])
    return (available <= signal)


def assert_no_lookahead_v392(
    df: pd.DataFrame,
    config: Optional[LookAheadConfigV392] = None,
) -> LookAheadAuditResultV392:
    """
    严格审计。

    如果失败，直接抛出 LookAheadViolation。
    """
    auditor = LookAheadAuditorV392(
        config or LookAheadConfigV392(strict=True)
    )
    result = auditor.audit(df)
    if not result.passed:
        raise LookAheadViolationV392(
            "Look-ahead audit failed: "
            f"{result.violation_count} violations."
        )
    return result


def audit_lookahead_v392(
    df: pd.DataFrame,
    config: Optional[LookAheadConfigV392] = None,
) -> LookAheadAuditResultV392:
    auditor = LookAheadAuditorV392(
        config or LookAheadConfigV392()
    )
    return auditor.audit(df)


# ============================================================
# Forward Return Builder
# ============================================================
def build_forward_return_v392(
    df: pd.DataFrame,
    *,
    code_column: str = "code",
    date_column: str = "date",
    price_column: str = "close",
    horizon: int = 1,
    output_column: str = "forward_return",
) -> pd.DataFrame:
    """
    构造未来收益。

    对于：

        close[t]

    horizon=1 时：

        return[t] =
            close[t+1] / close[t] - 1

    注意：

    这只是研究标签。

    如果实际策略规定：

        signal at t
        entry at t+1 open

    则不能直接把这个函数当成真实成交收益。
    """
    if horizon <= 0:
        raise ValueError("horizon must be > 0")
    required = [
        code_column,
        date_column,
        price_column,
    ]
    missing = [
        c for c in required if c not in df.columns
    ]
    if missing:
        raise LookAheadErrorV392(
            "Missing columns: "
            + ", ".join(missing)
        )
    work = df.copy()
    work[date_column] = (
        _normalize_date_series_v392(work[date_column])
    )
    work = work.sort_values(
        [code_column, date_column]
    ).copy()
    price = pd.to_numeric(
        work[price_column],
        errors="coerce",
    )
    future_price = (
        price.groupby(work[code_column]).shift(-horizon)
    )
    work[output_column] = (
        future_price / price - 1.0
    )
    work["_forward_horizon"] = (
        horizon
    )
    return work


# ============================================================
# Signal Lag Utility
# ============================================================
def lag_signal_v392(
    df: pd.DataFrame,
    *,
    code_column: str = "code",
    date_column: str = "date",
    signal_column: str = "signal",
    periods: int = 1,
    output_column: str = "lagged_signal",
) -> pd.DataFrame:
    """
    将 signal 向未来交易时点移动。

    periods=1：

        signal[t]
            ↓
        lagged_signal[t+1]

    这是防止 signal 与未来收益错误对齐的重要工具。
    """
    if periods < 0:
        raise ValueError("periods must be >= 0")
    required = [
        code_column,
        date_column,
        signal_column,
    ]
    missing = [
        c for c in required if c not in df.columns
    ]
    if missing:
        raise LookAheadErrorV392(
            "Missing columns: "
            + ", ".join(missing)
        )
    work = df.copy()
    work[date_column] = (
        _normalize_date_series_v392(work[date_column])
    )
    work = work.sort_values(
        [code_column, date_column]
    ).copy()
    work[output_column] = (
        work[signal_column]
        .groupby(work[code_column])
        .shift(periods)
    )
    return work


# ============================================================
# Rolling Safety Check
# ============================================================
def check_rolling_window_safety_v392(
    df: pd.DataFrame,
    *,
    code_column: str = "code",
    date_column: str = "date",
    source_column: str,
    rolling_column: str,
    window: int,
    min_periods: Optional[int] = None,
) -> LookAheadAuditResultV392:
    """
    检查 rolling feature 是否可能包含未来数据。

    对标准：

        series.groupby(code).rolling(window).mean()

    当前值只能使用：

        [t-window+1, ..., t]

    不允许使用：

        t+1, t+2, ...
    """
    if window <= 0:
        raise ValueError("window must be > 0")
    if min_periods is None:
        min_periods = window
    required = [
        code_column,
        date_column,
        source_column,
        rolling_column,
    ]
    missing = [
        c for c in required if c not in df.columns
    ]
    if missing:
        raise LookAheadErrorV392(
            "Missing columns: "
            + ", ".join(missing)
        )
    work = df.copy()
    work[date_column] = (
        _normalize_date_series_v392(work[date_column])
    )
    work = work.sort_values(
        [code_column, date_column]
    ).copy()
    expected = (
        work[source_column]
        .groupby(work[code_column])
        .rolling(
            window=window,
            min_periods=min_periods,
        )
        .mean()
        .reset_index(
            level=0,
            drop=True,
        )
    )
    expected = expected.reindex(work.index)
    actual = pd.to_numeric(
        work[rolling_column],
        errors="coerce",
    )
    comparison_mask = (
        expected.notna()
        & actual.notna()
    )
    difference = (
        expected - actual
    ).abs()
    bad = (
        difference > 1e-10
    ) & comparison_mask
    violations = []
    if bad.any():
        violations.append({
            "type": "rolling_mismatch",
            "count": int(bad.sum()),
            "message": (
                "Rolling feature differs "
                "from trailing-only calculation."
            ),
        })
    return LookAheadAuditResultV392(
        passed=len(violations) == 0,
        violation_count=len(violations),
        checked_rows=len(work),
        violations=violations,
        diagnostics={
            "window": window,
            "min_periods": min_periods,
            "source_column": source_column,
            "rolling_column": rolling_column,
        },
    )


# ============================================================
# Self Test
# ============================================================
def _self_test_v392() -> None:
    dates = pd.date_range(
        "2025-01-01",
        periods=5,
        freq="D",
    )
    # --------------------------------------------------------
    # Valid PIT
    # --------------------------------------------------------
    valid = pd.DataFrame({
        "code": [
            "000001",
            "000001",
            "000001",
            "000001",
            "000001",
        ],
        "date": dates,
        "available_date": dates,
        "signal_date": dates,
        "entry_date": dates + pd.Timedelta(days=1),
        "close": [10, 11, 12, 13, 14],
    })
    auditor = LookAheadAuditorV392(
        LookAheadConfigV392(strict=True)
    )
    # same observation dates are fine;
    # entry is next day
    result = auditor.audit(valid)
    assert result.passed

    # --------------------------------------------------------
    # Future available date
    # --------------------------------------------------------
    future = valid.copy()
    future.loc[2, "available_date"] = (
        future.loc[2, "signal_date"] + pd.Timedelta(days=5)
    )
    result = auditor.audit(future)
    assert not result.passed
    assert (result.violation_count >= 1)

    # --------------------------------------------------------
    # Signal / Entry same day
    # --------------------------------------------------------
    same_day = valid.copy()
    same_day.loc[1, "entry_date"] = same_day.loc[1, "signal_date"]
    result = auditor.audit(same_day)
    assert not result.passed

    # --------------------------------------------------------
    # Forward return
    # --------------------------------------------------------
    returns = build_forward_return_v392(
        valid,
        code_column="code",
        date_column="date",
        price_column="close",
        horizon=1,
    )
    expected = (11 / 10 - 1)
    assert abs(
        returns.loc[0, "forward_return"] - expected
    ) < 1e-10

    # --------------------------------------------------------
    # Signal lag
    # --------------------------------------------------------
    signal_df = valid[
        ["code", "date"]
    ].copy()
    signal_df["signal"] = np.arange(len(signal_df))
    lagged = lag_signal_v392(
        signal_df,
        periods=1,
    )
    assert pd.isna(lagged.iloc[0]["lagged_signal"])
    assert (lagged.iloc[1]["lagged_signal"] == 0)

    # --------------------------------------------------------
    # Rolling
    # --------------------------------------------------------
    rolling_df = valid[
        ["code", "date", "close"]
    ].copy()
    rolling_df["rolling_3"] = (
        rolling_df["close"]
        .rolling(3, min_periods=3)
        .mean()
    )
    rolling_result = (
        check_rolling_window_safety_v392(
            rolling_df,
            source_column="close",
            rolling_column="rolling_3",
            window=3,
        )
    )
    assert rolling_result.passed

    # --------------------------------------------------------
    # Available-date utility
    # --------------------------------------------------------
    mask = validate_available_date_v392(valid)
    assert mask.all()

    # --------------------------------------------------------
    # Signal-entry utility
    # --------------------------------------------------------
    mask = validate_signal_entry_dates_v392(valid)
    assert mask.all()

    print(
        "validation/lookahead.py "
        "self-test passed."
    )


if __name__ == "__main__":
    _self_test_v392()
