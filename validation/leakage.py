from __future__ import annotations

import pandas as pd


class LeakageDetector:
    def check_feature_target(
        self,
        df: pd.DataFrame,
        feature_columns: list[str],
        target_column: str,
        date_column: str = "date",
    ) -> dict:
        issues = []
        if date_column not in df.columns:
            issues.append("MISSING_DATE")
            return {
                "valid": False,
                "issues": issues,
            }
        dates = pd.to_datetime(df[date_column])
        if not dates.is_monotonic_increasing:
            issues.append("DATE_NOT_SORTED")
        if target_column not in df.columns:
            issues.append("MISSING_TARGET")
        for column in feature_columns:
            if column not in df.columns:
                issues.append(f"MISSING_FEATURE:{column}")
        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }
# ============================================================================
# V3.9.1 unified research engine - leakage checks (dump)
# ============================================================================


def leakage_checks(df: pd.DataFrame, target_col: str):
    errors = []
    if target_col not in df.columns:
        errors.append(f"缺少目标列{target_col}")
    if "date" not in df.columns:
        errors.append("缺少 date")
    if target_col in df.columns and not pd.api.types.is_numeric_dtype(df[target_col]):
        errors.append("target 必须为数值型")
    return errors


import pandas as pd  # noqa: E402


# ============================================================================
# V3.9.2 - Leakage Detection Engine (appended)
# ============================================================================

# -*- coding: utf-8 -*-
"""
AI Hedge Fund OS
V3.9.2 - Leakage Detection Engine (appended, V392 suffix)

职责：
1. 检查 Train / Validation / OOS 时间重叠
2. 检查 feature / label 时间污染
3. 检查标准化是否使用全样本
4. 检查 winsorization 是否使用全样本
5. 检查中性化 exposure 是否使用未来信息
6. 检查 target horizon 是否跨越数据切分边界
7. 检查同一股票的 train/validation/test 污染
8. 检查随机切分造成的时间泄漏
9. 检查 feature columns 是否包含未来字段
10. 输出结构化 Leakage Audit Report

核心原则：

    Feature(t)
        ↓
    Signal(t)
        ↓
    Trade(t+1)
        ↓
    Return(t+1 ... t+n)

任何：

    Feature(t) ← Data(t+1 ...)

都属于潜在泄漏。

另外：

    Train ← future Validation/OOS

也属于严重数据泄漏。
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================
# Exceptions
# ============================================================
class LeakageErrorV392(Exception):
    """Leakage 审计基础异常。"""


class LeakageViolationV392(LeakageErrorV392):
    """发现数据泄漏。"""


# ============================================================
# Configuration
# ============================================================
@dataclass
class LeakageConfigV392:
    """
    Leakage 审计配置。
    """
    code_column: str = "code"
    date_column: str = "date"
    available_date_column: str = "available_date"
    signal_date_column: str = "signal_date"
    label_date_column: str = "label_date"
    target_column: str = "forward_return"
    strict: bool = True
    require_time_order: bool = True
    require_disjoint_splits: bool = True
    allow_same_date_train_validation: bool = False
    check_feature_names: bool = True
    check_metadata: bool = True
    check_target_overlap: bool = True
    future_column_patterns: Sequence[str] = field(
        default_factory=lambda: (
            r"future",
            r"forward",
            r"next_",
            r"next$",
            r"lead",
            r"label",
            r"target",
            r"t\+",
            r"return_[0-9]+d",
        )
    )
    forbidden_feature_names: Sequence[str] = field(
        default_factory=lambda: (
            "future_return",
            "forward_return",
            "next_return",
            "next_close",
            "future_close",
            "future_high",
            "future_low",
            "future_volume",
            "target",
            "label",
        )
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Audit Result
# ============================================================
@dataclass
class LeakageAuditResultV392:
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
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)


# ============================================================
# Split Specification
# ============================================================
@dataclass
class TimeSplitV392:
    name: str
    start_date: Any
    end_date: Any
    label_horizon: int = 1
    embargo_days: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def normalized_start(self) -> pd.Timestamp:
        return pd.Timestamp(self.start_date).normalize()

    def normalized_end(self) -> pd.Timestamp:
        return pd.Timestamp(self.end_date).normalize()


# ============================================================
# Utilities
# ============================================================
def _normalize_date_v392(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _normalize_series_v392(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def _safe_float_v392(value: Any) -> Optional[float]:
    try:
        value = float(value)
        if not np.isfinite(value):
            return None
        return value
    except (TypeError, ValueError):
        return None


def _date_range_overlap_v392(
    start_a: pd.Timestamp,
    end_a: pd.Timestamp,
    start_b: pd.Timestamp,
    end_b: pd.Timestamp,
) -> bool:
    return (start_a <= end_b and start_b <= end_a)


# ============================================================
# Leakage Auditor
# ============================================================
class LeakageAuditorV392:
    def __init__(
        self,
        config: Optional[LeakageConfigV392] = None,
    ):
        self.config = (
            config or LeakageConfigV392()
        )

    # ========================================================
    # Main DataFrame Audit
    # ========================================================
    def audit(
        self,
        df: pd.DataFrame,
        *,
        feature_columns: Optional[Sequence[str]] = None,
        label_columns: Optional[Sequence[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LeakageAuditResultV392:
        if not isinstance(df, pd.DataFrame):
            raise LeakageErrorV392(
                "Input must be pandas DataFrame."
            )
        work = df.copy()
        violations: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        diagnostics: Dict[str, Any] = {}

        # ----------------------------------------------------
        # Required columns
        # ----------------------------------------------------
        self._check_required_columns_v392(
            work,
            violations,
        )
        if (
            violations
            and self.config.strict
        ):
            return LeakageAuditResultV392(
                passed=False,
                violation_count=len(violations),
                checked_rows=len(work),
                violations=violations,
                warnings=warnings,
                diagnostics=diagnostics,
            )

        # ----------------------------------------------------
        # Normalize date
        # ----------------------------------------------------
        for column in [
            self.config.date_column,
            self.config.available_date_column,
            self.config.signal_date_column,
            self.config.label_date_column,
        ]:
            if column in work.columns:
                work[column] = (
                    _normalize_series_v392(work[column])
                )

        # ----------------------------------------------------
        # Feature name audit
        # ----------------------------------------------------
        if feature_columns is not None:
            self._check_feature_columns_v392(
                feature_columns,
                violations,
                warnings,
            )

        # ----------------------------------------------------
        # PIT leakage
        # ----------------------------------------------------
        self._check_point_in_time_v392(
            work,
            violations,
            warnings,
        )

        # ----------------------------------------------------
        # Target leakage
        # ----------------------------------------------------
        if self.config.check_target_overlap:
            self._check_target_leakage_v392(
                work,
                violations,
                warnings,
            )

        # ----------------------------------------------------
        # Label columns
        # ----------------------------------------------------
        if label_columns is not None:
            self._check_label_columns_v392(
                label_columns,
                feature_columns,
                violations,
                warnings,
            )

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------
        if self.config.check_metadata:
            combined_metadata = dict(
                self.config.metadata
            )
            if metadata:
                combined_metadata.update(metadata)
            self._check_metadata_v392(
                combined_metadata,
                violations,
                warnings,
            )

        # ----------------------------------------------------
        # Basic diagnostics
        # ----------------------------------------------------
        if (
            self.config.date_column
            in work.columns
        ):
            date_values = (
                work[
                    self.config.date_column
                ].dropna()
            )
            if not date_values.empty:
                diagnostics["date_min"] = (
                    date_values.min()
                    .date()
                    .isoformat()
                )
                diagnostics["date_max"] = (
                    date_values.max()
                    .date()
                    .isoformat()
                )
            diagnostics["unique_codes"] = (
                int(
                    work[
                        self.config.code_column
                    ].nunique()
                )
                if self.config.code_column
                in work.columns
                else None
            )

        return LeakageAuditResultV392(
            passed=len(violations) == 0,
            violation_count=len(violations),
            warning_count=len(warnings),
            checked_rows=len(work),
            violations=violations,
            warnings=warnings,
            diagnostics=diagnostics,
        )

    # ========================================================
    # Required Columns
    # ========================================================
    def _check_required_columns_v392(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
    ) -> None:
        required = [
            self.config.code_column,
            self.config.date_column,
        ]
        for column in required:
            if column not in df.columns:
                violations.append({
                    "type": "missing_required_column",
                    "column": column,
                    "message": (
                        f"Required column missing: "
                        f"{column}"
                    ),
                })

    # ========================================================
    # Feature Names
    # ========================================================
    def _check_feature_columns_v392(
        self,
        feature_columns: Sequence[str],
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        patterns = [
            re.compile(
                pattern,
                flags=re.IGNORECASE,
            )
            for pattern
            in self.config.future_column_patterns
        ]
        forbidden = {
            str(x).lower()
            for x
            in self.config.forbidden_feature_names
        }
        for column in feature_columns:
            name = str(column)
            lower_name = (
                name.lower()
            )
            # Explicit forbidden names
            if lower_name in forbidden:
                violations.append({
                    "type": "forbidden_feature_name",
                    "column": name,
                    "message": (
                        "Feature name explicitly "
                        "indicates target/future data."
                    ),
                })
                continue
            # Pattern match
            matched = [
                pattern.pattern
                for pattern
                in patterns
                if pattern.search(lower_name)
            ]
            if matched:
                violations.append({
                    "type": "future_feature_pattern",
                    "column": name,
                    "matched_patterns": matched,
                    "message": (
                        "Feature name may contain "
                        "future/target information."
                    ),
                })

    # ========================================================
    # PIT
    # ========================================================
    def _check_point_in_time_v392(
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
        missing = (
            available_series.isna()
            & signal_series.notna()
        )
        if missing.any():
            target = (
                violations
                if self.config.strict
                else warnings
            )
            target.append({
                "type": "missing_pit_date",
                "count": int(
                    missing.sum()
                ),
                "message": (
                    "Rows have signal dates "
                    "but no available_date."
                ),
            })
        future = (
            available_series > signal_series
        )
        future &= (
            available_series.notna()
            & signal_series.notna()
        )
        if future.any():
            target = (
                violations
                if self.config.strict
                else warnings
            )
            target.append({
                "type": "pit_future_leakage",
                "count": int(
                    future.sum()
                ),
                "message": (
                    "Feature information became "
                    "available after signal date."
                ),
            })

    # ========================================================
    # Target Leakage
    # ========================================================
    def _check_target_leakage_v392(
        self,
        df: pd.DataFrame,
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        target = (
            self.config.target_column
        )
        date_col = (
            self.config.date_column
        )
        label_date = (
            self.config.label_date_column
        )
        if target not in df.columns:
            return

        # ----------------------------------------------------
        # If label_date exists, target must be after signal date
        # ----------------------------------------------------
        if (
            label_date in df.columns
            and self.config.signal_date_column
            in df.columns
        ):
            signal = df[
                self.config.signal_date_column
            ]
            label = df[label_date]
            invalid = (
                label <= signal
            )
            invalid &= (
                label.notna()
                & signal.notna()
            )
            if invalid.any():
                target_list = (
                    violations
                    if self.config.strict
                    else warnings
                )
                target_list.append({
                    "type": "target_before_signal",
                    "count": int(
                        invalid.sum()
                    ),
                    "message": (
                        "Label date is not after "
                        "signal date."
                    ),
                })

        # ----------------------------------------------------
        # Explicit target metadata
        # ----------------------------------------------------
        horizon = (
            self.config.metadata
            .get("target_horizon")
        )
        if horizon is not None:
            try:
                horizon = int(horizon)
                if horizon <= 0:
                    violations.append({
                        "type": "invalid_target_horizon",
                        "horizon": horizon,
                        "message": (
                            "Target horizon must "
                            "be positive."
                        ),
                    })
            except (TypeError, ValueError):
                violations.append({
                    "type": "invalid_target_horizon",
                    "horizon": horizon,
                    "message": (
                        "Target horizon must be integer."
                    ),
                })

    # ========================================================
    # Label Columns
    # ========================================================
    def _check_label_columns_v392(
        self,
        label_columns: Sequence[str],
        feature_columns: Optional[Sequence[str]],
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        if feature_columns is None:
            return
        feature_set = set(
            str(x)
            for x
            in feature_columns
        )
        overlap = (
            feature_set.intersection(
                set(
                    str(x)
                    for x
                    in label_columns
                )
            )
        )
        if overlap:
            violations.append({
                "type": "feature_label_overlap",
                "columns": sorted(overlap),
                "message": (
                    "Feature and label columns "
                    "overlap."
                ),
            })

    # ========================================================
    # Metadata
    # ========================================================
    def _check_metadata_v392(
        self,
        metadata: Dict[str, Any],
        violations: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
    ) -> None:
        # ----------------------------------------------------
        # Random split
        # ----------------------------------------------------
        split_method = str(
            metadata.get(
                "split_method",
                ""
            )
        ).lower()
        if split_method in {
            "random",
            "random_split",
            "shuffle",
            "shuffled",
        }:
            violations.append({
                "type": "random_time_split",
                "message": (
                    "Random/shuffled split is unsafe "
                    "for time-series alpha research."
                ),
            })

        # ----------------------------------------------------
        # Fit on full dataset
        # ----------------------------------------------------
        fit_scope = str(
            metadata.get(
                "fit_scope",
                ""
            )
        ).lower()
        if fit_scope in {
            "all",
            "full",
            "full_dataset",
            "entire_dataset",
        }:
            violations.append({
                "type": "full_dataset_fit",
                "message": (
                    "Transformer/model was fitted "
                    "on the full dataset."
                ),
            })

        # ----------------------------------------------------
        # Global normalization
        # ----------------------------------------------------
        normalization_scope = str(
            metadata.get(
                "normalization_scope",
                ""
            )
        ).lower()
        if normalization_scope in {
            "global",
            "all_data",
            "full_sample",
        }:
            violations.append({
                "type": "global_normalization",
                "message": (
                    "Normalization appears to use "
                    "the full sample."
                ),
            })

        # ----------------------------------------------------
        # Global winsorization
        # ----------------------------------------------------
        winsor_scope = str(
            metadata.get(
                "winsorization_scope",
                ""
            )
        ).lower()
        if winsor_scope in {
            "global",
            "all_data",
            "full_sample",
        }:
            violations.append({
                "type": "global_winsorization",
                "message": (
                    "Winsorization appears to use "
                    "the full sample."
                ),
            })

        # ----------------------------------------------------
        # Full-sample neutralization
        # ----------------------------------------------------
        neutral_scope = str(
            metadata.get(
                "neutralization_scope",
                ""
            )
        ).lower()
        if neutral_scope in {
            "global",
            "all_data",
            "full_sample",
        }:
            violations.append({
                "type": "global_neutralization",
                "message": (
                    "Neutralization appears to use "
                    "the full sample."
                ),
            })

        # ----------------------------------------------------
        # Future data explicitly declared
        # ----------------------------------------------------
        if metadata.get(
            "uses_future_data",
            False,
        ):
            violations.append({
                "type": "future_data_declared",
                "message": (
                    "Metadata explicitly declares "
                    "future data usage."
                ),
            })

    # ========================================================
    # Split Audit
    # ========================================================
    def audit_splits_v392(
        self,
        splits: Sequence[TimeSplitV392],
    ) -> LeakageAuditResultV392:
        violations: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        normalized = []
        for split in splits:
            start = split.normalized_start()
            end = split.normalized_end()
            if end < start:
                violations.append({
                    "type": "invalid_split_range",
                    "split": split.name,
                    "message": (
                        "Split end date is before "
                        "start date."
                    ),
                })
                continue
            normalized.append(
                (
                    split,
                    start,
                    end,
                )
            )

        # ----------------------------------------------------
        # Pairwise overlap
        # ----------------------------------------------------
        for i in range(len(normalized)):
            split_a, start_a, end_a = (
                normalized[i]
            )
            for j in range(
                i + 1,
                len(normalized),
            ):
                split_b, start_b, end_b = (
                    normalized[j]
                )
                if _date_range_overlap_v392(
                    start_a,
                    end_a,
                    start_b,
                    end_b,
                ):
                    violations.append({
                        "type": "split_overlap",
                        "split_a": split_a.name,
                        "split_b": split_b.name,
                        "message": (
                            "Train/validation/OOS "
                            "periods overlap."
                        ),
                    })

        # ----------------------------------------------------
        # Chronological order
        # ----------------------------------------------------
        if self.config.require_time_order:
            ordered = sorted(
                normalized,
                key=lambda x: x[1],
            )
            for i in range(
                len(ordered) - 1
            ):
                current = ordered[i]
                nxt = ordered[i + 1]
                current_split = current[0]
                current_end = current[2]
                next_split = nxt[0]
                next_start = nxt[1]
                if (
                    next_start <= current_end
                ):
                    violations.append({
                        "type": "non_chronological_split",
                        "previous": (
                            current_split.name
                        ),
                        "next": (
                            next_split.name
                        ),
                        "message": (
                            "Later split begins "
                            "before previous split ends."
                        ),
                    })

        # ----------------------------------------------------
        # Horizon crossing
        # ----------------------------------------------------
        if self.config.check_target_overlap:
            ordered = sorted(
                normalized,
                key=lambda x: x[1],
            )
            for i in range(
                len(ordered) - 1
            ):
                current_split = (
                    ordered[i][0]
                )
                current_end = (
                    ordered[i][2]
                )
                next_split = (
                    ordered[i + 1][0]
                )
                next_start = (
                    ordered[i + 1][1]
                )
                horizon = max(
                    1,
                    int(
                        current_split
                        .label_horizon
                    ),
                )
                embargo = max(
                    0,
                    int(
                        current_split
                        .embargo_days
                    ),
                )
                # Calendar-day conservative check.
                contamination_end = (
                    current_end
                    + pd.Timedelta(
                        days=horizon + embargo
                    )
                )
                if (
                    contamination_end
                    >= next_start
                ):
                    warnings.append({
                        "type": "label_horizon_near_split",
                        "split": (
                            current_split.name
                        ),
                        "next_split": (
                            next_split.name
                        ),
                        "label_horizon": horizon,
                        "embargo_days": embargo,
                        "message": (
                            "Target horizon may extend "
                            "into the next split. "
                            "Use purge/embargo."
                        ),
                    })

        return LeakageAuditResultV392(
            passed=len(violations) == 0,
            violation_count=len(violations),
            warning_count=len(warnings),
            checked_rows=len(splits),
            violations=violations,
            warnings=warnings,
            diagnostics={
                "split_count": len(splits),
            },
        )

    # ========================================================
    # Feature / Label Temporal Audit
    # ========================================================
    def audit_feature_label_alignment_v392(
        self,
        df: pd.DataFrame,
        *,
        feature_available_date_column: Optional[
            str
        ] = None,
        signal_date_column: Optional[
            str
        ] = None,
        label_date_column: Optional[
            str
        ] = None,
    ) -> LeakageAuditResultV392:
        feature_available_date_column = (
            feature_available_date_column
            or self.config
            .available_date_column
        )
        signal_date_column = (
            signal_date_column
            or self.config
            .signal_date_column
        )
        label_date_column = (
            label_date_column
            or self.config
            .label_date_column
        )
        violations = []
        warnings = []
        if (
            feature_available_date_column
            not in df.columns
        ):
            violations.append({
                "type": "missing_feature_available_date",
                "column": (
                    feature_available_date_column
                ),
            })
        if (
            signal_date_column
            not in df.columns
        ):
            violations.append({
                "type": "missing_signal_date",
                "column": signal_date_column,
            })
        if (
            label_date_column
            not in df.columns
        ):
            warnings.append({
                "type": "missing_label_date",
                "column": label_date_column,
                "message": (
                    "Cannot fully audit label "
                    "temporal alignment."
                ),
            })
        if violations:
            return LeakageAuditResultV392(
                passed=False,
                violation_count=len(violations),
                checked_rows=len(df),
                violations=violations,
                warnings=warnings,
            )
        feature_available = (
            _normalize_series_v392(
                df[
                    feature_available_date_column
                ]
            )
        )
        signal = (
            _normalize_series_v392(
                df[signal_date_column]
            )
        )
        bad_feature = (
            feature_available > signal
        )
        bad_feature &= (
            feature_available.notna()
            & signal.notna()
        )
        if bad_feature.any():
            violations.append({
                "type": "feature_available_after_signal",
                "count": int(
                    bad_feature.sum()
                ),
            })
        if (
            label_date_column
            in df.columns
        ):
            label = (
                _normalize_series_v392(
                    df[label_date_column]
                )
            )
            bad_label = (
                label <= signal
            )
            bad_label &= (
                label.notna()
                & signal.notna()
            )
            if bad_label.any():
                violations.append({
                    "type": "label_not_future",
                    "count": int(
                        bad_label.sum()
                    ),
                    "message": (
                        "Label date must occur "
                        "after signal date."
                    ),
                })
        return LeakageAuditResultV392(
            passed=len(violations) == 0,
            violation_count=len(violations),
            warning_count=len(warnings),
            checked_rows=len(df),
            violations=violations,
            warnings=warnings,
        )


# ============================================================
# Purged Time Split
# ============================================================
def build_purged_time_splits_v392(
    dates: Sequence[Any],
    *,
    train_size: float = 0.60,
    validation_size: float = 0.20,
    test_size: float = 0.20,
    label_horizon: int = 1,
    embargo_days: int = 0,
) -> List[TimeSplitV392]:
    """
    构建时间序列 Train / Validation / OOS。

    注意：
    这里使用日期而不是随机样本。

    purge / embargo：

        Train | gap | Validation | gap | OOS

    避免 label horizon 跨越切分边界。
    """
    if (
        train_size <= 0
        or validation_size <= 0
        or test_size <= 0
    ):
        raise ValueError(
            "Split sizes must be positive."
        )
    total = (
        train_size
        + validation_size
        + test_size
    )
    if abs(total - 1.0) > 1e-8:
        raise ValueError(
            "train_size + validation_size "
            "+ test_size must equal 1."
        )
    if label_horizon <= 0:
        raise ValueError(
            "label_horizon must be > 0."
        )
    unique_dates = sorted(
        set(
            _normalize_date_v392(x)
            for x in dates
            if pd.notna(x)
        )
    )
    if len(unique_dates) < 10:
        raise ValueError(
            "Not enough unique dates "
            "to create time splits."
        )
    n = len(unique_dates)
    train_end_idx = int(
        n * train_size
    ) - 1
    validation_end_idx = (
        train_end_idx
        + int(
            n * validation_size
        )
    )
    train_end_idx = max(
        0,
        min(
            train_end_idx,
            n - 1,
        ),
    )
    validation_end_idx = max(
        train_end_idx + 1,
        min(
            validation_end_idx,
            n - 1,
        ),
    )
    train_start = unique_dates[0]
    train_end = unique_dates[train_end_idx]
    validation_start_idx = (
        train_end_idx
        + 1
        + embargo_days
    )
    validation_start_idx = min(
        validation_start_idx,
        n - 1,
    )
    validation_start = unique_dates[
        validation_start_idx
    ]
    validation_end = unique_dates[
        validation_end_idx
    ]
    test_start_idx = (
        validation_end_idx
        + 1
        + embargo_days
    )
    test_start_idx = min(
        test_start_idx,
        n - 1,
    )
    test_start = unique_dates[test_start_idx]
    test_end = unique_dates[-1]
    return [
        TimeSplitV392(
            name="train",
            start_date=train_start,
            end_date=train_end,
            label_horizon=label_horizon,
            embargo_days=embargo_days,
        ),
        TimeSplitV392(
            name="validation",
            start_date=validation_start,
            end_date=validation_end,
            label_horizon=label_horizon,
            embargo_days=embargo_days,
        ),
        TimeSplitV392(
            name="oos",
            start_date=test_start,
            end_date=test_end,
            label_horizon=label_horizon,
            embargo_days=embargo_days,
        ),
    ]


# ============================================================
# Safe Transformer Metadata
# ============================================================
def validate_transformer_metadata_v392(
    metadata: Dict[str, Any],
) -> LeakageAuditResultV392:
    """
    专门检查：

    - scaler
    - winsorizer
    - neutralizer
    - imputer

    是否在 full sample 上 fit。
    """
    violations = []
    warnings = []
    transformer_names = (
        "scaler",
        "normalizer",
        "winsorizer",
        "neutralizer",
        "imputer",
        "transformer",
    )
    for name in transformer_names:
        item = metadata.get(name)
        if not isinstance(
            item,
            dict,
        ):
            continue
        fit_scope = str(
            item.get(
                "fit_scope",
                ""
            )
        ).lower()
        if fit_scope in {
            "all",
            "full",
            "full_sample",
            "all_data",
        }:
            violations.append({
                "type": "transformer_full_sample_fit",
                "transformer": name,
                "message": (
                    "Transformer fitted on "
                    "full dataset."
                ),
            })
        if item.get(
            "fit_on_oos",
            False,
        ):
            violations.append({
                "type": "transformer_fit_on_oos",
                "transformer": name,
                "message": (
                    "Transformer was fitted "
                    "using OOS data."
                ),
            })
    return LeakageAuditResultV392(
        passed=len(violations) == 0,
        violation_count=len(violations),
        warning_count=len(warnings),
        violations=violations,
        warnings=warnings,
    )


# ============================================================
# Convenience Functions
# ============================================================
def audit_leakage_v392(
    df: pd.DataFrame,
    *,
    feature_columns: Optional[
        Sequence[str]
    ] = None,
    label_columns: Optional[
        Sequence[str]
    ] = None,
    config: Optional[
        LeakageConfigV392
    ] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
) -> LeakageAuditResultV392:
    auditor = LeakageAuditorV392(
        config or LeakageConfigV392()
    )
    return auditor.audit(
        df,
        feature_columns=feature_columns,
        label_columns=label_columns,
        metadata=metadata,
    )


def assert_no_leakage_v392(
    df: pd.DataFrame,
    *,
    feature_columns: Optional[
        Sequence[str]
    ] = None,
    label_columns: Optional[
        Sequence[str]
    ] = None,
    config: Optional[
        LeakageConfigV392
    ] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
) -> LeakageAuditResultV392:
    result = audit_leakage_v392(
        df,
        feature_columns=feature_columns,
        label_columns=label_columns,
        config=config,
        metadata=metadata,
    )
    if not result.passed:
        raise LeakageViolationV392(
            "Leakage audit failed: "
            f"{result.violation_count} violations."
        )
    return result


def audit_time_splits_v392(
    splits: Sequence[TimeSplitV392],
    config: Optional[
        LeakageConfigV392
    ] = None,
) -> LeakageAuditResultV392:
    auditor = LeakageAuditorV392(
        config or LeakageConfigV392()
    )
    return auditor.audit_splits_v392(
        splits
    )


# ============================================================
# Self Test
# ============================================================
def _self_test_v392() -> None:
    dates = pd.date_range(
        "2025-01-01",
        periods=30,
        freq="D",
    )
    # --------------------------------------------------------
    # Valid dataset
    # --------------------------------------------------------
    df = pd.DataFrame({
        "code": [
            "000001"
        ] * len(dates),
        "date": dates,
        "available_date": dates,
        "signal_date": dates,
        "label_date": (
            dates
            + pd.Timedelta(
                days=1
            )
        ),
        "close": (
            np.arange(len(dates))
            + 10
        ),
        "momentum_20": (
            np.random.default_rng(42)
            .normal(
                size=len(dates)
            )
        ),
        "forward_return": (
            np.random.default_rng(43)
            .normal(
                size=len(dates)
            )
        ),
    })
    config = LeakageConfigV392(
        strict=True
    )
    auditor = LeakageAuditorV392(
        config
    )
    result = auditor.audit(
        df,
        feature_columns=[
            "momentum_20"
        ],
        label_columns=[
            "forward_return"
        ],
    )
    assert result.passed

    # --------------------------------------------------------
    # PIT leakage
    # --------------------------------------------------------
    future_pit = df.copy()
    future_pit.loc[
        5,
        "available_date"
    ] = (
        future_pit.loc[
            5,
            "signal_date"
        ]
        + pd.Timedelta(
            days=5
        )
    )
    result = auditor.audit(
        future_pit,
        feature_columns=[
            "momentum_20"
        ],
        label_columns=[
            "forward_return"
        ],
    )
    assert not result.passed

    # --------------------------------------------------------
    # Future feature name
    # --------------------------------------------------------
    result = auditor.audit(
        df,
        feature_columns=[
            "momentum_20",
            "future_return",
        ],
        label_columns=[
            "forward_return"
        ],
    )
    assert not result.passed

    # --------------------------------------------------------
    # Feature / label overlap
    # --------------------------------------------------------
    result = auditor.audit(
        df,
        feature_columns=[
            "momentum_20",
            "forward_return",
        ],
        label_columns=[
            "forward_return"
        ],
    )
    assert not result.passed

    # --------------------------------------------------------
    # Random split
    # --------------------------------------------------------
    result = auditor.audit(
        df,
        feature_columns=[
            "momentum_20"
        ],
        metadata={
            "split_method": "random",
        },
    )
    assert not result.passed

    # --------------------------------------------------------
    # Full sample scaler
    # --------------------------------------------------------
    result = validate_transformer_metadata_v392({
        "scaler": {
            "fit_scope": "full_sample"
        }
    })
    assert not result.passed

    # --------------------------------------------------------
    # Time splits
    # --------------------------------------------------------
    splits = [
        TimeSplitV392(
            "train",
            "2025-01-01",
            "2025-01-15",
            label_horizon=1,
        ),
        TimeSplitV392(
            "validation",
            "2025-01-17",
            "2025-01-22",
            label_horizon=1,
        ),
        TimeSplitV392(
            "oos",
            "2025-01-24",
            "2025-01-30",
            label_horizon=1,
        ),
    ]
    split_result = (
        auditor
        .audit_splits_v392(
            splits
        )
    )
    assert split_result.passed

    # --------------------------------------------------------
    # Overlapping split
    # --------------------------------------------------------
    bad_splits = [
        TimeSplitV392(
            "train",
            "2025-01-01",
            "2025-01-20",
        ),
        TimeSplitV392(
            "validation",
            "2025-01-15",
            "2025-01-25",
        ),
        TimeSplitV392(
            "oos",
            "2025-01-26",
            "2025-01-30",
        ),
    ]
    split_result = (
        auditor
        .audit_splits_v392(
            bad_splits
        )
    )
    assert not split_result.passed

    # --------------------------------------------------------
    # Purged splits
    # --------------------------------------------------------
    generated = (
        build_purged_time_splits_v392(
            dates,
            train_size=0.6,
            validation_size=0.2,
            test_size=0.2,
            label_horizon=1,
            embargo_days=1,
        )
    )
    assert len(generated) == 3

    print(
        "validation/leakage.py "
        "self-test passed."
    )


if __name__ == "__main__":
    _self_test_v392()
