from __future__ import annotations

import pandas as pd


class TemporalValidator:
    def validate(
        self,
        df: pd.DataFrame,
        feature_date: str,
        label_date: str,
    ) -> dict:
        work = df.copy()
        work[feature_date] = pd.to_datetime(work[feature_date])
        work[label_date] = pd.to_datetime(work[label_date])
        violations = work[work[feature_date] >= work[label_date]]
        return {
            "valid": violations.empty,
            "violations": len(violations),
        }



# ============================================================================
# V3.9.1 unified research engine - temporal validation
# ============================================================================


def validate_temporal(panel: pd.DataFrame) -> list[str]:
    """时间顺序校验：date 必须单调、无重复（code 内）。"""
    errors: list[str] = []
    if panel is None or panel.empty:
        return errors
    if "date" not in panel.columns:
        errors.append("panel 缺少 date 列")
        return errors
    if "code" not in panel.columns:
        errors.append("panel 缺少 code 列")
        return errors
    for code, group in panel.groupby("code", sort=False):
        dates = pd.to_datetime(group["date"])
        if not dates.is_monotonic_increasing:
            errors.append(f"{code}: date 非单调")
        if dates.duplicated().any():
            errors.append(f"{code}: date 存在重复")
    return errors


# ============================================================================
# V3.9.2 temporal validation - strict time-series split, purge, embargo
# ============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


class TemporalValidationErrorV392(Exception):
    """Base exception for temporal validation."""


class TemporalBoundaryErrorV392(TemporalValidationErrorV392):
    """Raised when temporal boundaries are invalid."""


class TemporalSplitTypeV392(str, Enum):
    """
    Supported temporal split styles.
    """
    EXPANDING = "expanding"
    ROLLING = "rolling"
    FIXED = "fixed"


@dataclass
class TemporalConfigV392:
    """
    Configuration for temporal validation.

    All dates are normalized to calendar dates.

    Important:
        This module does not randomly shuffle observations.

    The temporal order is always:

        past -> present -> future
    """
    date_column: str = "date"
    min_train_periods: int = 60
    validation_periods: int = 20
    test_periods: int = 20
    step_periods: int = 20
    embargo_periods: int = 0
    purge_periods: int = 0
    split_type: TemporalSplitTypeV392 = TemporalSplitTypeV392.EXPANDING
    allow_empty_validation: bool = False
    allow_empty_test: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalWindowV392:
    """
    One temporal research window.
    """
    window_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: Optional[pd.Timestamp] = None
    validation_end: Optional[pd.Timestamp] = None
    test_start: Optional[pd.Timestamp] = None
    test_end: Optional[pd.Timestamp] = None
    purge_start: Optional[pd.Timestamp] = None
    purge_end: Optional[pd.Timestamp] = None
    embargo_start: Optional[pd.Timestamp] = None
    embargo_end: Optional[pd.Timestamp] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def train_dates(self) -> Tuple[pd.Timestamp, pd.Timestamp]:
        return self.train_start, self.train_end

    def validation_dates(
        self,
    ) -> Optional[Tuple[pd.Timestamp, pd.Timestamp]]:
        if (
            self.validation_start is None
            or self.validation_end is None
        ):
            return None
        return (
            self.validation_start,
            self.validation_end,
        )

    def test_dates(
        self,
    ) -> Optional[Tuple[pd.Timestamp, pd.Timestamp]]:
        if (
            self.test_start is None
            or self.test_end is None
        ):
            return None
        return (
            self.test_start,
            self.test_end,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "train_start": self.train_start.strftime("%Y-%m-%d"),
            "train_end": self.train_end.strftime("%Y-%m-%d"),
            "validation_start": (
                None
                if self.validation_start is None
                else self.validation_start.strftime("%Y-%m-%d")
            ),
            "validation_end": (
                None
                if self.validation_end is None
                else self.validation_end.strftime("%Y-%m-%d")
            ),
            "test_start": (
                None
                if self.test_start is None
                else self.test_start.strftime("%Y-%m-%d")
            ),
            "test_end": (
                None
                if self.test_end is None
                else self.test_end.strftime("%Y-%m-%d")
            ),
            "purge_start": (
                None
                if self.purge_start is None
                else self.purge_start.strftime("%Y-%m-%d")
            ),
            "purge_end": (
                None
                if self.purge_end is None
                else self.purge_end.strftime("%Y-%m-%d")
            ),
            "embargo_start": (
                None
                if self.embargo_start is None
                else self.embargo_start.strftime("%Y-%m-%d")
            ),
            "embargo_end": (
                None
                if self.embargo_end is None
                else self.embargo_end.strftime("%Y-%m-%d")
            ),
            "metadata": self.metadata,
        }


@dataclass
class TemporalAuditResultV392:
    """
    Result of temporal validation.
    """
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "diagnostics": self.diagnostics,
        }

    def raise_if_failed(self) -> None:
        if not self.passed:
            message = (
                "Temporal validation failed:\n"
                + "\n".join(self.errors)
            )
            raise TemporalBoundaryErrorV392(message)


def normalize_date_v392(
    value: Any,
) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError(f"Invalid date: {value}")
    return result.normalize()


def normalize_dates_v392(
    dates: Iterable[Any],
) -> pd.DatetimeIndex:
    result = pd.to_datetime(
        list(dates),
        errors="coerce",
    )
    result = pd.DatetimeIndex(result).normalize()
    result = result[~result.isna()]
    return result.sort_values().unique()


def unique_sorted_dates_v392(
    data: pd.DataFrame,
    date_column: str = "date",
) -> pd.DatetimeIndex:
    if date_column not in data.columns:
        raise ValueError(
            f"Missing date column: {date_column}"
        )
    dates = pd.to_datetime(
        data[date_column],
        errors="coerce",
    ).dt.normalize()
    dates = dates.dropna()
    return pd.DatetimeIndex(sorted(dates.unique()))


class TemporalValidatorV392:
    """
    Strict temporal ordering validator.

    Main guarantees:

        train_end < validation_start
        validation_end < test_start

    Optional:

        purge gap
        embargo gap

    This class is deliberately independent of:
        - market data vendor
        - factor implementation
        - ML framework
        - backtest engine
    """

    def __init__(
        self,
        config: Optional[TemporalConfigV392] = None,
    ) -> None:
        self.config = (
            config
            or TemporalConfigV392()
        )
        self._validate_config()

    # --------------------------------------------------------
    # Config
    # --------------------------------------------------------
    def _validate_config(self) -> None:
        if self.config.min_train_periods <= 0:
            raise ValueError("min_train_periods must be > 0")
        if self.config.validation_periods < 0:
            raise ValueError("validation_periods must be >= 0")
        if self.config.test_periods < 0:
            raise ValueError("test_periods must be >= 0")
        if self.config.step_periods <= 0:
            raise ValueError("step_periods must be > 0")
        if self.config.purge_periods < 0:
            raise ValueError("purge_periods must be >= 0")
        if self.config.embargo_periods < 0:
            raise ValueError("embargo_periods must be >= 0")

    # --------------------------------------------------------
    # Dataset Validation
    # --------------------------------------------------------
    def validate_dataset(
        self,
        data: pd.DataFrame,
    ) -> TemporalAuditResultV392:
        errors: List[str] = []
        warnings: List[str] = []
        if data is None:
            errors.append("Dataset is None.")
            return TemporalAuditResultV392(
                passed=False,
                errors=errors,
                warnings=warnings,
            )
        if self.config.date_column not in data.columns:
            errors.append(
                f"Missing date column: {self.config.date_column}"
            )
            return TemporalAuditResultV392(
                passed=False,
                errors=errors,
                warnings=warnings,
            )
        dates = pd.to_datetime(
            data[
                self.config.date_column
            ],
            errors="coerce",
        )
        invalid_dates = int(
            dates.isna().sum()
        )
        if invalid_dates:
            errors.append(
                f"Found {invalid_dates} invalid dates."
            )
        normalized = dates.dropna().dt.normalize()
        if len(normalized) > 1:
            if not normalized.is_monotonic_increasing:
                warnings.append(
                    "Input data is not sorted "
                    "chronologically."
                )
        unique_dates = sorted(
            normalized.unique()
        )
        duplicate_date_count = (
            len(normalized)
            - len(unique_dates)
        )
        diagnostics = {
            "rows": len(data),
            "unique_dates": len(unique_dates),
            "invalid_dates": invalid_dates,
            "duplicate_date_rows": (
                duplicate_date_count
            ),
            "min_date": (
                None
                if not unique_dates
                else pd.Timestamp(
                    unique_dates[0]
                ).strftime("%Y-%m-%d")
            ),
            "max_date": (
                None
                if not unique_dates
                else pd.Timestamp(
                    unique_dates[-1]
                ).strftime("%Y-%m-%d")
            ),
        }
        return TemporalAuditResultV392(
            passed=not errors,
            errors=errors,
            warnings=warnings,
            diagnostics=diagnostics,
        )

    # --------------------------------------------------------
    # Basic Boundary Check
    # --------------------------------------------------------
    @staticmethod
    def validate_window(
        window: TemporalWindowV392,
    ) -> TemporalAuditResultV392:
        errors = []
        warnings = []
        if (
            window.train_start
            > window.train_end
        ):
            errors.append("train_start > train_end")
        if (
            window.validation_start is not None
            and window.validation_end is not None
            and window.validation_start
            > window.validation_end
        ):
            errors.append(
                "validation_start > validation_end"
            )
        if (
            window.test_start is not None
            and window.test_end is not None
            and window.test_start
            > window.test_end
        ):
            errors.append("test_start > test_end")
        # Train / validation separation
        if (
            window.validation_start is not None
            and window.train_end
            >= window.validation_start
        ):
            errors.append(
                "Training and validation periods overlap."
            )
        # Validation / test separation
        if (
            window.validation_end is not None
            and window.test_start is not None
            and window.validation_end
            >= window.test_start
        ):
            errors.append(
                "Validation and test periods overlap."
            )
        # If no validation, train must precede test.
        if (
            window.validation_start is None
            and window.test_start is not None
            and window.train_end
            >= window.test_start
        ):
            errors.append(
                "Training and test periods overlap."
            )
        # Purge consistency
        if (
            window.purge_start is not None
            and window.purge_end is not None
        ):
            if (
                window.purge_start
                > window.purge_end
            ):
                errors.append("purge_start > purge_end")
            if (
                window.purge_start
                <= window.train_end
            ):
                errors.append(
                    "Purge period overlaps training."
                )
        # Embargo consistency
        if (
            window.embargo_start is not None
            and window.embargo_end is not None
        ):
            if (
                window.embargo_start
                > window.embargo_end
            ):
                errors.append(
                    "embargo_start > embargo_end"
                )
        # Test should be after embargo.
        if (
            window.embargo_end is not None
            and window.test_start is not None
            and window.embargo_end
            >= window.test_start
        ):
            warnings.append(
                "Embargo reaches test start; "
                "check whether this is intentional."
            )
        return TemporalAuditResultV392(
            passed=not errors,
            errors=errors,
            warnings=warnings,
            diagnostics={
                "window_id": window.window_id,
            },
        )

    # --------------------------------------------------------
    # Generate Windows
    # --------------------------------------------------------
    def generate_windows(
        self,
        dates: Sequence[Any],
    ) -> List[TemporalWindowV392]:
        normalized = normalize_dates_v392(dates)
        if len(normalized) == 0:
            return []
        min_train = (
            self.config.min_train_periods
        )
        validation_n = (
            self.config.validation_periods
        )
        test_n = (
            self.config.test_periods
        )
        step = (
            self.config.step_periods
        )
        windows: List[TemporalWindowV392] = []
        start_train_end_index = (
            min_train - 1
        )
        if (
            start_train_end_index
            >= len(normalized)
        ):
            return []
        window_id = 0
        train_end_index = (
            start_train_end_index
        )
        while True:
            # --------------------------------------------
            # Train
            # --------------------------------------------
            if (
                self.config.split_type
                == TemporalSplitTypeV392.ROLLING
            ):
                train_start_index = max(
                    0,
                    train_end_index
                    - min_train
                    + 1,
                )
            elif (
                self.config.split_type
                == TemporalSplitTypeV392.FIXED
            ):
                train_start_index = 0
            else:
                # EXPANDING
                train_start_index = 0
            train_end = normalized[
                train_end_index
            ]
            train_start = normalized[
                train_start_index
            ]
            # --------------------------------------------
            # Validation
            # --------------------------------------------
            validation_start_index = (
                train_end_index
                + 1
            )
            if validation_n > 0:
                validation_end_index = (
                    validation_start_index
                    + validation_n
                    - 1
                )
                if (
                    validation_end_index
                    >= len(normalized)
                ):
                    break
                validation_start = normalized[
                    validation_start_index
                ]
                validation_end = normalized[
                    validation_end_index
                ]
            else:
                validation_start = None
                validation_end = None
                validation_end_index = (
                    train_end_index
                )
            # --------------------------------------------
            # Purge
            # --------------------------------------------
            purge_start = None
            purge_end = None
            if self.config.purge_periods > 0:
                purge_start_index = (
                    train_end_index
                    + 1
                )
                purge_end_index = (
                    purge_start_index
                    + self.config.purge_periods
                    - 1
                )
                if (
                    purge_end_index
                    >= len(normalized)
                ):
                    break
                purge_start = normalized[
                    purge_start_index
                ]
                purge_end = normalized[
                    purge_end_index
                ]
            # --------------------------------------------
            # Embargo
            # --------------------------------------------
            embargo_start = None
            embargo_end = None
            if self.config.embargo_periods > 0:
                if validation_n > 0:
                    embargo_start_index = (
                        validation_end_index
                        + 1
                    )
                else:
                    embargo_start_index = (
                        train_end_index
                        + 1
                    )
                embargo_end_index = (
                    embargo_start_index
                    + self.config.embargo_periods
                    - 1
                )
                if (
                    embargo_end_index
                    >= len(normalized)
                ):
                    break
                embargo_start = normalized[
                    embargo_start_index
                ]
                embargo_end = normalized[
                    embargo_end_index
                ]
            # --------------------------------------------
            # Test
            # --------------------------------------------
            if test_n > 0:
                test_start_index = (
                    train_end_index
                    + 1
                )
                if validation_n > 0:
                    test_start_index = (
                        validation_end_index
                        + 1
                    )
                if (
                    self.config.purge_periods > 0
                    and validation_n == 0
                ):
                    test_start_index = (
                        train_end_index
                        + self.config.purge_periods
                        + 1
                    )
                if (
                    self.config.embargo_periods > 0
                ):
                    test_start_index = (
                        embargo_end_index
                        + 1
                    )
                test_end_index = (
                    test_start_index
                    + test_n
                    - 1
                )
                if (
                    test_end_index
                    >= len(normalized)
                ):
                    break
                test_start = normalized[
                    test_start_index
                ]
                test_end = normalized[
                    test_end_index
                ]
            else:
                test_start = None
                test_end = None
            # --------------------------------------------
            # Window
            # --------------------------------------------
            window = TemporalWindowV392(
                window_id=window_id,
                train_start=train_start,
                train_end=train_end,
                validation_start=(
                    validation_start
                ),
                validation_end=(
                    validation_end
                ),
                test_start=test_start,
                test_end=test_end,
                purge_start=purge_start,
                purge_end=purge_end,
                embargo_start=embargo_start,
                embargo_end=embargo_end,
                metadata={
                    "split_type": (
                        self.config.split_type.value
                        if isinstance(
                            self.config.split_type,
                            TemporalSplitTypeV392,
                        )
                        else str(
                            self.config.split_type
                        )
                    ),
                    "train_periods": (
                        min_train
                    ),
                    "validation_periods": (
                        validation_n
                    ),
                    "test_periods": (
                        test_n
                    ),
                },
            )
            audit = self.validate_window(
                window
            )
            if not audit.passed:
                raise TemporalBoundaryErrorV392(
                    "Invalid temporal window "
                    f"{window_id}: "
                    + "; ".join(audit.errors)
                )
            windows.append(window)
            window_id += 1
            # --------------------------------------------
            # Advance
            # --------------------------------------------
            train_end_index += step
            if (
                train_end_index
                >= len(normalized)
            ):
                break
        return windows

    # --------------------------------------------------------
    # Generate From DataFrame
    # --------------------------------------------------------
    def generate_from_dataframe(
        self,
        data: pd.DataFrame,
    ) -> List[TemporalWindowV392]:
        audit = self.validate_dataset(
            data
        )
        audit.raise_if_failed()
        dates = unique_sorted_dates_v392(
            data,
            self.config.date_column,
        )
        return self.generate_windows(
            dates
        )

    # --------------------------------------------------------
    # Assign Split Labels
    # --------------------------------------------------------
    def assign_window_labels(
        self,
        data: pd.DataFrame,
        window: TemporalWindowV392,
    ) -> pd.DataFrame:
        if (
            self.config.date_column
            not in data.columns
        ):
            raise ValueError(
                f"Missing date column: {self.config.date_column}"
            )
        df = data.copy()
        dates = pd.to_datetime(
            df[
                self.config.date_column
            ],
            errors="coerce",
        ).dt.normalize()
        df[
            "temporal_split"
        ] = "unused"
        # Train
        train_mask = (
            dates
            >= window.train_start
        ) & (
            dates
            <= window.train_end
        )
        df.loc[
            train_mask,
            "temporal_split",
        ] = "train"
        # Validation
        if (
            window.validation_start
            is not None
            and window.validation_end
            is not None
        ):
            validation_mask = (
                dates
                >= window.validation_start
            ) & (
                dates
                <= window.validation_end
            )
            df.loc[
                validation_mask,
                "temporal_split",
            ] = "validation"
        # Test
        if (
            window.test_start
            is not None
            and window.test_end
            is not None
        ):
            test_mask = (
                dates
                >= window.test_start
            ) & (
                dates
                <= window.test_end
            )
            df.loc[
                test_mask,
                "temporal_split",
            ] = "test"
        # Purge
        if (
            window.purge_start
            is not None
            and window.purge_end
            is not None
        ):
            purge_mask = (
                dates
                >= window.purge_start
            ) & (
                dates
                <= window.purge_end
            )
            df.loc[
                purge_mask,
                "temporal_split",
            ] = "purged"
        # Embargo
        if (
            window.embargo_start
            is not None
            and window.embargo_end
            is not None
        ):
            embargo_mask = (
                dates
                >= window.embargo_start
            ) & (
                dates
                <= window.embargo_end
            )
            df.loc[
                embargo_mask,
                "temporal_split",
            ] = "embargo"
        return df

    # --------------------------------------------------------
    # Extract Split
    # --------------------------------------------------------
    def extract_window(
        self,
        data: pd.DataFrame,
        window: TemporalWindowV392,
    ) -> Dict[
        str,
        pd.DataFrame,
    ]:
        labeled = self.assign_window_labels(
            data,
            window,
        )
        return {
            "train": labeled[
                labeled[
                    "temporal_split"
                ]
                == "train"
            ].copy(),
            "validation": labeled[
                labeled[
                    "temporal_split"
                ]
                == "validation"
            ].copy(),
            "test": labeled[
                labeled[
                    "temporal_split"
                ]
                == "test"
            ].copy(),
            "purged": labeled[
                labeled[
                    "temporal_split"
                ]
                == "purged"
            ].copy(),
            "embargo": labeled[
                labeled[
                    "temporal_split"
                ]
                == "embargo"
            ].copy(),
            "unused": labeled[
                labeled[
                    "temporal_split"
                ]
                == "unused"
            ].copy(),
        }

    # --------------------------------------------------------
    # Full Temporal Audit
    # --------------------------------------------------------
    def audit_windows(
        self,
        windows: Sequence[TemporalWindowV392],
    ) -> TemporalAuditResultV392:
        errors = []
        warnings = []
        previous_test_end = None
        for window in windows:
            result = self.validate_window(
                window
            )
            errors.extend(
                result.errors
            )
            warnings.extend(
                result.warnings
            )
            # Walk-forward windows should move
            # forward in time.
            if (
                previous_test_end
                is not None
                and window.test_end
                is not None
            ):
                if (
                    window.test_end
                    <= previous_test_end
                ):
                    errors.append(
                        "Temporal windows are "
                        "not strictly increasing."
                    )
            if window.test_end is not None:
                previous_test_end = (
                    window.test_end
                )
        return TemporalAuditResultV392(
            passed=not errors,
            errors=errors,
            warnings=warnings,
            diagnostics={
                "window_count": len(
                    windows
                ),
            },
        )


# ============================================================
# Convenience Functions
# ============================================================
def build_temporal_windows_v392(
    dates: Sequence[Any],
    *,
    min_train_periods: int = 60,
    validation_periods: int = 20,
    test_periods: int = 20,
    step_periods: int = 20,
    purge_periods: int = 0,
    embargo_periods: int = 0,
    split_type: TemporalSplitTypeV392 = (
        TemporalSplitTypeV392.EXPANDING
    ),
) -> List[TemporalWindowV392]:
    config = TemporalConfigV392(
        min_train_periods=min_train_periods,
        validation_periods=validation_periods,
        test_periods=test_periods,
        step_periods=step_periods,
        purge_periods=purge_periods,
        embargo_periods=embargo_periods,
        split_type=split_type,
    )
    validator = TemporalValidatorV392(
        config
    )
    return validator.generate_windows(
        dates
    )


def temporal_audit_v392(
    data: pd.DataFrame,
    *,
    date_column: str = "date",
) -> TemporalAuditResultV392:
    config = TemporalConfigV392(
        date_column=date_column
    )
    validator = TemporalValidatorV392(
        config
    )
    return validator.validate_dataset(
        data
    )


def validate_temporal_windows_v392(
    windows: Sequence[TemporalWindowV392],
) -> TemporalAuditResultV392:
    validator = TemporalValidatorV392()
    return validator.audit_windows(
        windows
    )


# ============================================================
# Self Test
# ============================================================
def _self_test_v392() -> None:
    dates = pd.date_range(
        "2020-01-01",
        periods=200,
        freq="D",
    )
    config = TemporalConfigV392(
        min_train_periods=60,
        validation_periods=20,
        test_periods=20,
        step_periods=20,
        purge_periods=2,
        embargo_periods=2,
        split_type=(
            TemporalSplitTypeV392.EXPANDING
        ),
    )
    validator = TemporalValidatorV392(
        config
    )
    windows = validator.generate_windows(
        dates
    )
    assert len(windows) > 0
    # --------------------------------------------------------
    # Validate first window
    # --------------------------------------------------------
    first = windows[
        0
    ]
    result = validator.validate_window(
        first
    )
    assert result.passed
    assert (
        first.train_end
        < first.validation_start
    )
    assert (
        first.validation_end
        < first.embargo_start
        or first.embargo_start
        is None
    )
    assert (
        first.embargo_end
        < first.test_start
        or first.embargo_end
        is None
    )
    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------
    data = pd.DataFrame(
        {
            "date": dates,
            "code": [
                "000001"
            ]
            * len(dates),
            "feature": np.arange(
                len(dates)
            ),
            "target": np.arange(
                len(dates)
            )
            + 1,
        }
    )
    dataset_audit = (
        validator.validate_dataset(
            data
        )
    )
    assert dataset_audit.passed
    # --------------------------------------------------------
    # Extract
    # --------------------------------------------------------
    splits = validator.extract_window(
        data,
        first,
    )
    assert len(
        splits[
            "train"
        ]
    ) > 0
    assert len(
        splits[
            "validation"
        ]
    ) > 0
    assert len(
        splits[
            "test"
        ]
    ) > 0
    # Purge and embargo should exist.
    assert len(
        splits[
            "purged"
        ]
    ) == 2
    assert len(
        splits[
            "embargo"
        ]
    ) == 2
    # --------------------------------------------------------
    # Ensure no overlap
    # --------------------------------------------------------
    train_dates = set(
        splits[
            "train"
        ][
            "date"
        ]
    )
    validation_dates = set(
        splits[
            "validation"
        ][
            "date"
        ]
    )
    test_dates = set(
        splits[
            "test"
        ][
            "date"
        ]
    )
    assert (
        train_dates
        & validation_dates
    ) == set()
    assert (
        validation_dates
        & test_dates
    ) == set()
    assert (
        train_dates
        & test_dates
    ) == set()
    # --------------------------------------------------------
    # Window audit
    # --------------------------------------------------------
    audit = validator.audit_windows(
        windows
    )
    assert audit.passed
    # --------------------------------------------------------
    # Rolling test
    # --------------------------------------------------------
    rolling_validator = (
        TemporalValidatorV392(
            TemporalConfigV392(
                min_train_periods=30,
                validation_periods=10,
                test_periods=10,
                step_periods=10,
                split_type=(
                    TemporalSplitTypeV392.ROLLING
                ),
            )
        )
    )
    rolling_windows = (
        rolling_validator.generate_windows(
            dates
        )
    )
    assert len(
        rolling_windows
    ) > 0
    assert (
        rolling_windows[
            0
        ].train_start
        == dates[
            0
        ]
    )
    if len(
        rolling_windows
    ) > 1:
        assert (
            rolling_windows[
                1
            ].train_start
            > rolling_windows[
                0
            ].train_start
        )
    print("validation/temporal.py V392 self-test passed.")


if __name__ == "__main__":
    _self_test_v392()
