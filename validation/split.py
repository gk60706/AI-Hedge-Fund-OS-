

# ============================================================================
# V3.9.2 Temporal Data Splitter - strict time-series split for panel data
# ============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


class SplitErrorV392(Exception):
    """基础 Split 异常。"""


class SplitConfigErrorV392(SplitErrorV392):
    """Split 配置错误。"""


class SplitBoundaryErrorV392(SplitErrorV392):
    """时间边界错误。"""


class SplitLeakageErrorV392(SplitErrorV392):
    """检测到数据泄漏。"""


class SplitTypeV392(str, Enum):
    """
    时间切分方式。
    """
    EXPANDING = "expanding"
    ROLLING = "rolling"
    FIXED = "fixed"


class DatasetPartV392(str, Enum):
    """
    数据集部分。
    """
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    PURGED = "purged"
    EMBARGO = "embargo"


@dataclass
class SplitConfigV392:
    """
    时间切分配置。
    """
    date_column: str = "date"
    code_column: str = "code"
    signal_date_column: Optional[str] = None
    target_date_column: Optional[str] = None
    split_type: SplitTypeV392 = SplitTypeV392.EXPANDING
    # Train
    min_train_periods: int = 60
    # Validation
    validation_periods: int = 20
    # Test
    test_periods: int = 20
    # 每次窗口向前移动多少个交易日
    step_periods: int = 20
    # 手工 Purge
    purge_periods: int = 0
    # 手工 Embargo
    embargo_periods: int = 0
    # 如果没有 target_date_column，
    # 可以通过 label_horizon 指定标签未来周期。
    label_horizon: int = 0
    # 是否要求 date + code 唯一
    require_unique_date_code: bool = True
    # 是否允许 validation 为空
    allow_empty_validation: bool = False
    # 是否允许 test 为空
    allow_empty_test: bool = False
    # 是否保留原始 index
    preserve_index: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.split_type, str):
            self.split_type = SplitTypeV392(
                self.split_type
            )
        if self.min_train_periods <= 0:
            raise SplitConfigErrorV392(
                "min_train_periods 必须 > 0"
            )
        if self.validation_periods < 0:
            raise SplitConfigErrorV392(
                "validation_periods 不能 < 0"
            )
        if self.test_periods < 0:
            raise SplitConfigErrorV392(
                "test_periods 不能 < 0"
            )
        if self.step_periods <= 0:
            raise SplitConfigErrorV392(
                "step_periods 必须 > 0"
            )
        if self.purge_periods < 0:
            raise SplitConfigErrorV392(
                "purge_periods 不能 < 0"
            )
        if self.embargo_periods < 0:
            raise SplitConfigErrorV392(
                "embargo_periods 不能 < 0"
            )
        if self.label_horizon < 0:
            raise SplitConfigErrorV392(
                "label_horizon 不能 < 0"
            )


@dataclass
class SplitWindowV392:
    """
    一个完整的研究窗口。
    """
    split_id: int
    train_dates: Tuple[pd.Timestamp, ...]
    purge_dates: Tuple[pd.Timestamp, ...]
    validation_dates: Tuple[pd.Timestamp, ...]
    embargo_dates: Tuple[pd.Timestamp, ...]
    test_dates: Tuple[pd.Timestamp, ...]
    split_type: SplitTypeV392
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def train_start(self) -> Optional[pd.Timestamp]:
        return self.train_dates[
            0
        ] if self.train_dates else None

    @property
    def train_end(self) -> Optional[pd.Timestamp]:
        return self.train_dates[
            -1
        ] if self.train_dates else None

    @property
    def validation_start(
        self,
    ) -> Optional[pd.Timestamp]:
        return (
            self.validation_dates[
                0
            ]
            if self.validation_dates
            else None
        )

    @property
    def validation_end(
        self,
    ) -> Optional[pd.Timestamp]:
        return (
            self.validation_dates[
                -1
            ]
            if self.validation_dates
            else None
        )

    @property
    def test_start(self) -> Optional[pd.Timestamp]:
        return self.test_dates[
            0
        ] if self.test_dates else None

    @property
    def test_end(self) -> Optional[pd.Timestamp]:
        return self.test_dates[
            -1
        ] if self.test_dates else None

    def dates(
        self,
        part: DatasetPartV392,
    ) -> Tuple[pd.Timestamp, ...]:
        if part == DatasetPartV392.TRAIN:
            return self.train_dates
        if part == DatasetPartV392.VALIDATION:
            return self.validation_dates
        if part == DatasetPartV392.TEST:
            return self.test_dates
        if part == DatasetPartV392.PURGED:
            return self.purge_dates
        if part == DatasetPartV392.EMBARGO:
            return self.embargo_dates
        raise ValueError(
            f"未知 DatasetPart: {part}"
        )

    def to_dict(self) -> Dict[str, Any]:
        def fmt(
            dates: Tuple[pd.Timestamp, ...],
        ) -> List[str]:
            return [
                d.strftime("%Y-%m-%d")
                for d in dates
            ]

        return {
            "split_id": self.split_id,
            "split_type": self.split_type.value,
            "train_start": (
                self.train_start.strftime(
                    "%Y-%m-%d"
                )
                if self.train_start
                is not None
                else None
            ),
            "train_end": (
                self.train_end.strftime(
                    "%Y-%m-%d"
                )
                if self.train_end
                is not None
                else None
            ),
            "validation_start": (
                self.validation_start.strftime(
                    "%Y-%m-%d"
                )
                if self.validation_start
                is not None
                else None
            ),
            "validation_end": (
                self.validation_end.strftime(
                    "%Y-%m-%d"
                )
                if self.validation_end
                is not None
                else None
            ),
            "test_start": (
                self.test_start.strftime(
                    "%Y-%m-%d"
                )
                if self.test_start
                is not None
                else None
            ),
            "test_end": (
                self.test_end.strftime(
                    "%Y-%m-%d"
                )
                if self.test_end
                is not None
                else None
            ),
            "train_count": len(
                self.train_dates
            ),
            "purge_count": len(
                self.purge_dates
            ),
            "validation_count": len(
                self.validation_dates
            ),
            "embargo_count": len(
                self.embargo_dates
            ),
            "test_count": len(
                self.test_dates
            ),
            "train_dates": fmt(
                self.train_dates
            ),
            "purge_dates": fmt(
                self.purge_dates
            ),
            "validation_dates": fmt(
                self.validation_dates
            ),
            "embargo_dates": fmt(
                self.embargo_dates
            ),
            "test_dates": fmt(
                self.test_dates
            ),
            "metadata": self.metadata,
        }


@dataclass
class DataSplitV392:
    """
    一个具体窗口对应的数据切分结果。
    """
    window: SplitWindowV392
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    purged: pd.DataFrame
    embargo: pd.DataFrame
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "split_id": self.window.split_id,
            "train_rows": len(self.train),
            "validation_rows": len(
                self.validation
            ),
            "test_rows": len(self.test),
            "purged_rows": len(self.purged),
            "embargo_rows": len(
                self.embargo
            ),
            "train_dates": len(
                self.window.train_dates
            ),
            "validation_dates": len(
                self.window.validation_dates
            ),
            "test_dates": len(
                self.window.test_dates
            ),
            "metadata": self.metadata,
        }


@dataclass
class SplitAuditResultV392:
    """
    Split 审计结果。
    """
    passed: bool = True
    errors: List[str] = field(
        default_factory=list
    )
    warnings: List[str] = field(
        default_factory=list
    )
    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )

    def add_error(
        self,
        message: str,
    ) -> None:
        self.errors.append(message)
        self.passed = False

    def add_warning(
        self,
        message: str,
    ) -> None:
        self.warnings.append(message)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def summary(self) -> str:
        status = (
            "PASSED"
            if self.passed
            else "FAILED"
        )
        return (
            f"SplitAudit[{status}] "
            f"errors={self.error_count}, "
            f"warnings={self.warning_count}"
        )

    def raise_if_failed(self) -> None:
        if not self.passed:
            raise SplitLeakageErrorV392(
                self.summary()
                + "\n"
                + "\n".join(self.errors)
            )


def _normalize_dates_v392(
    values: Iterable[Any],
) -> pd.DatetimeIndex:
    """
    标准化日期。
    """
    result = pd.to_datetime(
        pd.Series(list(values)),
        errors="coerce",
    )
    if result.isna().any():
        raise SplitConfigErrorV392(
            "数据中存在无法解析的日期。"
        )
    return pd.DatetimeIndex(
        result.dt.normalize()
    )


def _unique_sorted_dates_v392(
    df: pd.DataFrame,
    date_column: str,
) -> pd.DatetimeIndex:
    dates = _normalize_dates_v392(
        df[date_column].tolist()
    )
    return pd.DatetimeIndex(
        sorted(dates.unique())
    )


class TemporalDataSplitterV392:
    """
    V3.9.2 标准时间数据切分器。

    特点：
    - Cross-sectional safe
    - No random split
    - Purge
    - Embargo
    - Expanding
    - Rolling
    - Fixed
    - Label horizon audit
    """

    def __init__(
        self,
        config: Optional[SplitConfigV392] = None,
    ) -> None:
        self.config = (
            config or SplitConfigV392()
        )

    # --------------------------------------------------------
    # Prepare
    # --------------------------------------------------------
    def prepare(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if not isinstance(
            df,
            pd.DataFrame,
        ):
            raise TypeError(
                "df 必须是 pandas.DataFrame"
            )
        if df.empty:
            raise SplitConfigErrorV392(
                "输入数据为空。"
            )
        date_col = (
            self.config.date_column
        )
        if date_col not in df.columns:
            raise SplitConfigErrorV392(
                f"缺少日期字段: {date_col}"
            )
        result = df.copy()
        result[date_col] = pd.to_datetime(
            result[date_col],
            errors="coerce",
        ).dt.normalize()
        if result[date_col].isna().any():
            raise SplitConfigErrorV392(
                f"{date_col} 存在无法解析的日期。"
            )
        code_col = (
            self.config.code_column
        )
        if code_col in result.columns:
            result[code_col] = (
                result[code_col]
                .astype(str)
                .str.strip()
            )
        if self.config.require_unique_date_code:
            if code_col not in result.columns:
                raise SplitConfigErrorV392(
                    f"要求 date + code 唯一，但缺少 {code_col}"
                )
            duplicate_mask = result.duplicated(
                subset=[date_col, code_col],
                keep=False,
            )
            if duplicate_mask.any():
                duplicate_count = int(
                    duplicate_mask.sum()
                )
                raise SplitConfigErrorV392(
                    "发现重复的 date + code 记录: "
                    f"{duplicate_count} 行"
                )
        sort_columns = [date_col]
        if code_col in result.columns:
            sort_columns.append(code_col)
        result = result.sort_values(
            sort_columns
        )
        if not self.config.preserve_index:
            result = result.reset_index(
                drop=True
            )
        return result

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------
    def get_dates(
        self,
        df: pd.DataFrame,
    ) -> pd.DatetimeIndex:
        prepared = self.prepare(df)
        return _unique_sorted_dates_v392(
            prepared,
            self.config.date_column,
        )

    # --------------------------------------------------------
    # Effective purge
    # --------------------------------------------------------
    def effective_purge_periods(self) -> int:
        """
        计算最终 Purge 周期。

        如果 label_horizon 大于 purge_periods，
        自动采用更大的值。
        """
        return max(
            self.config.purge_periods,
            self.config.label_horizon,
        )

    # --------------------------------------------------------
    # Window generation
    # --------------------------------------------------------
    def generate_windows(
        self,
        df: pd.DataFrame,
    ) -> List[SplitWindowV392]:
        prepared = self.prepare(df)
        dates = _unique_sorted_dates_v392(
            prepared,
            self.config.date_column,
        )
        n = len(dates)
        min_train = (
            self.config.min_train_periods
        )
        validation = (
            self.config.validation_periods
        )
        test = self.config.test_periods
        step = self.config.step_periods
        purge = self.effective_purge_periods()
        embargo = (
            self.config.embargo_periods
        )
        if n < min_train:
            raise SplitBoundaryErrorV392(
                f"有效交易日只有 {n} 个，"
                f"不足最小训练周期 {min_train}。"
            )
        windows: List[SplitWindowV392] = []
        split_id = 0
        # ====================================================
        # EXPANDING
        # ====================================================
        if (
            self.config.split_type
            == SplitTypeV392.EXPANDING
        ):
            train_end = min_train - 1
            while True:
                validation_start = (
                    train_end + 1 + purge
                )
                validation_end = (
                    validation_start
                    + validation
                    - 1
                )
                test_start = (
                    validation_end
                    + 1
                    + embargo
                )
                test_end = (
                    test_start + test - 1
                )
                if validation > 0:
                    if validation_end >= n:
                        break
                else:
                    validation_start = (
                        train_end + 1
                    )
                    validation_end = train_end
                if test > 0 and test_end >= n:
                    break
                train_dates = tuple(
                    dates[: train_end + 1]
                )
                purge_dates = tuple(
                    dates[
                        train_end + 1 : validation_start
                    ]
                )
                validation_dates = (
                    tuple(
                        dates[
                            validation_start : validation_end
                            + 1
                        ]
                    )
                    if validation > 0
                    else tuple()
                )
                embargo_dates = (
                    tuple(
                        dates[
                            validation_end + 1 : test_start
                        ]
                    )
                    if test > 0
                    else tuple()
                )
                test_dates = (
                    tuple(
                        dates[
                            test_start : test_end
                            + 1
                        ]
                    )
                    if test > 0
                    else tuple()
                )
                if (
                    not validation_dates
                    and not self.config.allow_empty_validation
                ):
                    break
                if (
                    not test_dates
                    and not self.config.allow_empty_test
                ):
                    break
                windows.append(
                    SplitWindowV392(
                        split_id=split_id,
                        train_dates=train_dates,
                        purge_dates=purge_dates,
                        validation_dates=validation_dates,
                        embargo_dates=embargo_dates,
                        test_dates=test_dates,
                        split_type=self.config.split_type,
                        metadata={
                            "train_periods": len(
                                train_dates
                            ),
                            "purge_periods": len(
                                purge_dates
                            ),
                            "validation_periods": len(
                                validation_dates
                            ),
                            "embargo_periods": len(
                                embargo_dates
                            ),
                            "test_periods": len(
                                test_dates
                            ),
                        },
                    )
                )
                split_id += 1
                train_end += step
                if train_end >= n:
                    break
        # ====================================================
        # ROLLING
        # ====================================================
        elif (
            self.config.split_type
            == SplitTypeV392.ROLLING
        ):
            train_end = min_train - 1
            while True:
                train_start = (
                    train_end
                    - min_train
                    + 1
                )
                validation_start = (
                    train_end + 1 + purge
                )
                validation_end = (
                    validation_start
                    + validation
                    - 1
                )
                test_start = (
                    validation_end
                    + 1
                    + embargo
                )
                test_end = (
                    test_start + test - 1
                )
                if validation > 0:
                    if validation_end >= n:
                        break
                if test > 0:
                    if test_end >= n:
                        break
                train_dates = tuple(
                    dates[
                        train_start : train_end
                        + 1
                    ]
                )
                purge_dates = tuple(
                    dates[
                        train_end + 1 : validation_start
                    ]
                )
                validation_dates = (
                    tuple(
                        dates[
                            validation_start : validation_end
                            + 1
                        ]
                    )
                    if validation > 0
                    else tuple()
                )
                embargo_dates = (
                    tuple(
                        dates[
                            validation_end + 1 : test_start
                        ]
                    )
                    if test > 0
                    else tuple()
                )
                test_dates = (
                    tuple(
                        dates[
                            test_start : test_end
                            + 1
                        ]
                    )
                    if test > 0
                    else tuple()
                )
                windows.append(
                    SplitWindowV392(
                        split_id=split_id,
                        train_dates=train_dates,
                        purge_dates=purge_dates,
                        validation_dates=validation_dates,
                        embargo_dates=embargo_dates,
                        test_dates=test_dates,
                        split_type=self.config.split_type,
                        metadata={
                            "train_periods": len(
                                train_dates
                            ),
                            "purge_periods": len(
                                purge_dates
                            ),
                            "validation_periods": len(
                                validation_dates
                            ),
                            "embargo_periods": len(
                                embargo_dates
                            ),
                            "test_periods": len(
                                test_dates
                            ),
                        },
                    )
                )
                split_id += 1
                train_end += step
                if train_end >= n:
                    break
        # ====================================================
        # FIXED
        # ====================================================
        elif (
            self.config.split_type
            == SplitTypeV392.FIXED
        ):
            # Fixed = 训练集永远固定为最早的
            # min_train_periods 个交易日。
            #
            # 后续窗口只向前移动 validation/test。
            train_start = 0
            train_end = min_train - 1
            validation_start = (
                train_end + 1 + purge
            )
            while True:
                validation_end = (
                    validation_start
                    + validation
                    - 1
                )
                test_start = (
                    validation_end
                    + 1
                    + embargo
                )
                test_end = (
                    test_start + test - 1
                )
                if validation > 0:
                    if validation_end >= n:
                        break
                if test > 0:
                    if test_end >= n:
                        break
                train_dates = tuple(
                    dates[
                        train_start : train_end
                        + 1
                    ]
                )
                purge_dates = tuple(
                    dates[
                        train_end + 1 : validation_start
                    ]
                )
                validation_dates = (
                    tuple(
                        dates[
                            validation_start : validation_end
                            + 1
                        ]
                    )
                    if validation > 0
                    else tuple()
                )
                embargo_dates = (
                    tuple(
                        dates[
                            validation_end + 1 : test_start
                        ]
                    )
                    if test > 0
                    else tuple()
                )
                test_dates = (
                    tuple(
                        dates[
                            test_start : test_end
                            + 1
                        ]
                    )
                    if test > 0
                    else tuple()
                )
                windows.append(
                    SplitWindowV392(
                        split_id=split_id,
                        train_dates=train_dates,
                        purge_dates=purge_dates,
                        validation_dates=validation_dates,
                        embargo_dates=embargo_dates,
                        test_dates=test_dates,
                        split_type=self.config.split_type,
                        metadata={
                            "fixed_train": True,
                            "train_periods": len(
                                train_dates
                            ),
                            "purge_periods": len(
                                purge_dates
                            ),
                            "validation_periods": len(
                                validation_dates
                            ),
                            "embargo_periods": len(
                                embargo_dates
                            ),
                            "test_periods": len(
                                test_dates
                            ),
                        },
                    )
                )
                split_id += 1
                validation_start += step
                if validation_start >= n:
                    break
        else:
            raise SplitConfigErrorV392(
                f"不支持的 split_type: "
                f"{self.config.split_type}"
            )
        if not windows:
            raise SplitBoundaryErrorV392(
                "无法生成有效的时间窗口。"
                "请检查数据长度、train/validation/test "
                "周期以及 purge/embargo 设置。"
            )
        return windows

    # --------------------------------------------------------
    # Split one window
    # --------------------------------------------------------
    def split_by_window(
        self,
        df: pd.DataFrame,
        window: SplitWindowV392,
    ) -> DataSplitV392:
        prepared = self.prepare(df)
        date_col = (
            self.config.date_column
        )
        train_set = set(
            window.train_dates
        )
        purge_set = set(
            window.purge_dates
        )
        validation_set = set(
            window.validation_dates
        )
        embargo_set = set(
            window.embargo_dates
        )
        test_set = set(
            window.test_dates
        )
        date_values = pd.to_datetime(
            prepared[date_col]
        ).dt.normalize()
        train_mask = date_values.isin(
            train_set
        )
        purge_mask = date_values.isin(
            purge_set
        )
        validation_mask = (
            date_values.isin(validation_set)
        )
        embargo_mask = date_values.isin(
            embargo_set
        )
        test_mask = date_values.isin(
            test_set
        )
        train = prepared.loc[
            train_mask
        ].copy()
        purge = prepared.loc[
            purge_mask
        ].copy()
        validation = prepared.loc[
            validation_mask
        ].copy()
        embargo_df = prepared.loc[
            embargo_mask
        ].copy()
        test = prepared.loc[
            test_mask
        ].copy()
        result = DataSplitV392(
            window=window,
            train=train,
            validation=validation,
            test=test,
            purged=purge,
            embargo=embargo_df,
            metadata={
                "split_id": window.split_id,
                "train_rows": len(train),
                "validation_rows": len(
                    validation
                ),
                "test_rows": len(test),
                "purged_rows": len(purge),
                "embargo_rows": len(
                    embargo_df
                ),
            },
        )
        return result

    # --------------------------------------------------------
    # Split all
    # --------------------------------------------------------
    def split_all(
        self,
        df: pd.DataFrame,
    ) -> List[DataSplitV392]:
        prepared = self.prepare(df)
        windows = self.generate_windows(
            prepared
        )
        return [
            self.split_by_window(
                prepared,
                window,
            )
            for window in windows
        ]

    # --------------------------------------------------------
    # Target date leakage audit
    # --------------------------------------------------------
    def audit_target_dates(
        self,
        split: DataSplitV392,
    ) -> SplitAuditResultV392:
        result = SplitAuditResultV392()
        target_col = (
            self.config.target_date_column
        )
        if not target_col:
            return result
        if target_col not in split.train.columns:
            result.add_warning(
                f"Train 中不存在 target_date_column: "
                f"{target_col}"
            )
            return result
        target_dates = pd.to_datetime(
            split.train[target_col],
            errors="coerce",
        ).dt.normalize()
        if target_dates.isna().any():
            result.add_error(
                "Train target_date 存在无法解析的日期。"
            )
            return result
        # ----------------------------------------------------
        # Train label 不允许进入 Validation/Test
        # ----------------------------------------------------
        if (
            split.window.validation_start
            is not None
        ):
            overlap_mask = (
                target_dates
                >= split.window.validation_start
            )
            if overlap_mask.any():
                result.add_error(
                    "检测到 Train label horizon "
                    "跨越 Validation 边界。"
                    f"违规行数={int(overlap_mask.sum())}"
                )
        if split.window.test_start is not None:
            overlap_mask = (
                target_dates
                >= split.window.test_start
            )
            if overlap_mask.any():
                result.add_error(
                    "检测到 Train label horizon "
                    "跨越 Test 边界。"
                    f"违规行数={int(overlap_mask.sum())}"
                )
        return result

    # --------------------------------------------------------
    # Generic split audit
    # --------------------------------------------------------
    def audit_split(
        self,
        split: DataSplitV392,
    ) -> SplitAuditResultV392:
        result = SplitAuditResultV392()
        window = split.window
        # ====================================================
        # 1. Date overlap
        # ====================================================
        train_dates = set(
            window.train_dates
        )
        purge_dates = set(
            window.purge_dates
        )
        validation_dates = set(
            window.validation_dates
        )
        embargo_dates = set(
            window.embargo_dates
        )
        test_dates = set(
            window.test_dates
        )
        groups = {
            "train": train_dates,
            "purge": purge_dates,
            "validation": validation_dates,
            "embargo": embargo_dates,
            "test": test_dates,
        }
        names = list(groups.keys())
        for i in range(len(names)):
            for j in range(
                i + 1,
                len(names),
            ):
                left = names[i]
                right = names[j]
                overlap = (
                    groups[left]
                    & groups[right]
                )
                if overlap:
                    result.add_error(
                        f"时间窗口重叠: "
                        f"{left} vs {right}; "
                        f"overlap={len(overlap)}"
                    )
        # ====================================================
        # 2. Chronological order
        # ====================================================
        if window.train_end is not None:
            if window.purge_dates:
                if (
                    window.purge_dates[0]
                    <= window.train_end
                ):
                    result.add_error(
                        "Purge 没有严格位于 Train 之后。"
                    )
            if window.validation_dates:
                if (
                    window.validation_dates[0]
                    <= window.train_end
                ):
                    result.add_error(
                        "Validation 没有严格位于 Train 之后。"
                    )
        if window.validation_end is not None:
            if window.embargo_dates:
                if (
                    window.embargo_dates[0]
                    <= window.validation_end
                ):
                    result.add_error(
                        "Embargo 没有严格位于 Validation 之后。"
                    )
            if window.test_dates:
                if (
                    window.test_dates[0]
                    <= window.validation_end
                ):
                    result.add_error(
                        "Test 没有严格位于 Validation 之后。"
                    )
        # ====================================================
        # 3. Train / Test overlap
        # ====================================================
        if train_dates & test_dates:
            result.add_error(
                "Train 与 Test 存在时间重叠。"
            )
        # ====================================================
        # 4. DataFrame date overlap
        # ====================================================
        date_col = (
            self.config.date_column
        )
        train_actual = set(
            pd.to_datetime(
                split.train[date_col]
            )
            .dt.normalize()
            .unique()
        )
        validation_actual = set(
            pd.to_datetime(
                split.validation[date_col]
            )
            .dt.normalize()
            .unique()
        )
        test_actual = set(
            pd.to_datetime(
                split.test[date_col]
            )
            .dt.normalize()
            .unique()
        )
        if train_actual != train_dates:
            result.add_error(
                "Train DataFrame 日期集合 "
                "与 SplitWindow 不一致。"
            )
        if validation_actual != validation_dates:
            if validation_dates:
                result.add_error(
                    "Validation DataFrame 日期集合 "
                    "与 SplitWindow 不一致。"
                )
        if test_actual != test_dates:
            if test_dates:
                result.add_error(
                    "Test DataFrame 日期集合 "
                    "与 SplitWindow 不一致。"
                )
        # ====================================================
        # 5. Empty checks
        # ====================================================
        if (
            split.validation.empty
            and not self.config.allow_empty_validation
            and window.validation_dates
        ):
            result.add_error(
                "Validation 日期存在，但 DataFrame 为空。"
            )
        if (
            split.test.empty
            and not self.config.allow_empty_test
            and window.test_dates
        ):
            result.add_error(
                "Test 日期存在，但 DataFrame 为空。"
            )
        # ====================================================
        # 6. Target date audit
        # ====================================================
        target_result = self.audit_target_dates(
            split
        )
        result.errors.extend(
            target_result.errors
        )
        result.warnings.extend(
            target_result.warnings
        )
        if target_result.errors:
            result.passed = False
        # ====================================================
        # Diagnostics
        # ====================================================
        result.diagnostics.update(
            {
                "split_id": window.split_id,
                "split_type": window.split_type.value,
                "train_rows": len(split.train),
                "validation_rows": len(
                    split.validation
                ),
                "test_rows": len(split.test),
                "purged_rows": len(
                    split.purged
                ),
                "embargo_rows": len(
                    split.embargo
                ),
                "train_periods": len(
                    window.train_dates
                ),
                "validation_periods": len(
                    window.validation_dates
                ),
                "test_periods": len(
                    window.test_dates
                ),
            }
        )
        return result

    # --------------------------------------------------------
    # Audit all
    # --------------------------------------------------------
    def audit_all(
        self,
        splits: Sequence[DataSplitV392],
    ) -> SplitAuditResultV392:
        result = SplitAuditResultV392()
        previous_test_end: Optional[
            pd.Timestamp
        ] = None
        for split in splits:
            current = self.audit_split(
                split
            )
            result.errors.extend(
                [
                    f"split={split.window.split_id}: "
                    f"{e}"
                    for e in current.errors
                ]
            )
            result.warnings.extend(
                [
                    f"split={split.window.split_id}: "
                    f"{w}"
                    for w in current.warnings
                ]
            )
            test_end = split.window.test_end
            if (
                previous_test_end is not None
                and test_end is not None
                and test_end
                <= previous_test_end
            ):
                result.add_error(
                    "不同 Walk-Forward 窗口的 Test "
                    "结束时间没有向前推进。"
                )
            if test_end is not None:
                previous_test_end = test_end
        if result.errors:
            result.passed = False
        result.diagnostics[
            "window_count"
        ] = len(splits)
        return result


# ============================================================
# Convenience Functions
# ============================================================
def build_temporal_splits_v392(
    df: pd.DataFrame,
    config: Optional[
        SplitConfigV392
    ] = None,
) -> List[DataSplitV392]:
    splitter = TemporalDataSplitterV392(
        config=config
    )
    return splitter.split_all(df)


def split_time_series_v392(
    df: pd.DataFrame,
    config: Optional[
        SplitConfigV392
    ] = None,
) -> List[DataSplitV392]:
    return build_temporal_splits_v392(
        df,
        config=config,
    )


def audit_splits_v392(
    splits: Sequence[DataSplitV392],
    config: Optional[
        SplitConfigV392
    ] = None,
) -> SplitAuditResultV392:
    splitter = TemporalDataSplitterV392(
        config=config
    )
    return splitter.audit_all(splits)


def assert_valid_splits_v392(
    splits: Sequence[DataSplitV392],
    config: Optional[
        SplitConfigV392
    ] = None,
) -> None:
    result = audit_splits_v392(
        splits,
        config=config,
    )
    result.raise_if_failed()


# ============================================================
# Debug / Summary
# ============================================================
def summarize_splits_v392(
    splits: Sequence[DataSplitV392],
) -> pd.DataFrame:
    rows: List[
        Dict[str, Any]
    ] = []
    for split in splits:
        window = split.window
        rows.append(
            {
                "split_id": window.split_id,
                "split_type": window.split_type.value,
                "train_start": (
                    window.train_start
                ),
                "train_end": (
                    window.train_end
                ),
                "purge_start": (
                    window.purge_dates[0]
                    if window.purge_dates
                    else None
                ),
                "purge_end": (
                    window.purge_dates[-1]
                    if window.purge_dates
                    else None
                ),
                "validation_start": (
                    window.validation_start
                ),
                "validation_end": (
                    window.validation_end
                ),
                "embargo_start": (
                    window.embargo_dates[0]
                    if window.embargo_dates
                    else None
                ),
                "embargo_end": (
                    window.embargo_dates[-1]
                    if window.embargo_dates
                    else None
                ),
                "test_start": (
                    window.test_start
                ),
                "test_end": (
                    window.test_end
                ),
                "train_rows": len(split.train),
                "validation_rows": len(
                    split.validation
                ),
                "test_rows": len(split.test),
            }
        )
    return pd.DataFrame(rows)


# ============================================================
# Self Test
# ============================================================
def _build_demo_panel_v392(
    periods: int = 180,
    stocks: int = 10,
) -> pd.DataFrame:
    dates = pd.bdate_range(
        "2024-01-01",
        periods=periods,
    )
    rows = []
    for date in dates:
        for i in range(stocks):
            code = (
                f"{600000 + i:06d}"
            )
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "close": 10.0 + i,
                    "target_date": (
                        date
                        + pd.Timedelta(
                            days=5
                        )
                    ),
                }
            )
    return pd.DataFrame(rows)


def self_test_v392() -> None:
    """
    模块自检。
    """
    df = _build_demo_panel_v392()
    # ========================================================
    # Expanding
    # ========================================================
    config = SplitConfigV392(
        split_type=SplitTypeV392.EXPANDING,
        min_train_periods=60,
        validation_periods=20,
        test_periods=20,
        step_periods=20,
        purge_periods=5,
        embargo_periods=3,
        target_date_column="target_date",
        label_horizon=5,
    )
    splitter = TemporalDataSplitterV392(
        config
    )
    splits = splitter.split_all(df)
    assert len(splits) > 0
    audit = splitter.audit_all(splits)
    # target_date 是自然日 + 5，
    # 但 purge 使用交易日概念。
    #
    # 这里仅验证结构，不要求 demo target_date
    # 与交易日完全一致。
    #
    # 因此只检查基础 split。
    assert all(
        len(s.train) > 0
        for s in splits
    )
    assert all(
        len(s.validation) > 0
        for s in splits
    )
    assert all(
        len(s.test) > 0
        for s in splits
    )
    # ========================================================
    # Rolling
    # ========================================================
    rolling_config = SplitConfigV392(
        split_type=SplitTypeV392.ROLLING,
        min_train_periods=60,
        validation_periods=20,
        test_periods=20,
        step_periods=20,
        purge_periods=5,
        embargo_periods=3,
    )
    rolling_splitter = TemporalDataSplitterV392(
        rolling_config
    )
    rolling_splits = (
        rolling_splitter.split_all(df)
    )
    assert len(rolling_splits) > 0
    for split in rolling_splits:
        assert (
            len(
                split.window.train_dates
            )
            == 60
        )
    # ========================================================
    # Fixed
    # ========================================================
    fixed_config = SplitConfigV392(
        split_type=SplitTypeV392.FIXED,
        min_train_periods=60,
        validation_periods=20,
        test_periods=20,
        step_periods=20,
        purge_periods=5,
        embargo_periods=3,
    )
    fixed_splitter = TemporalDataSplitterV392(
        fixed_config
    )
    fixed_splits = fixed_splitter.split_all(
        df
    )
    assert len(fixed_splits) > 0
    for split in fixed_splits:
        assert (
            len(
                split.window.train_dates
            )
            == 60
        )
    # ========================================================
    # Date disjointness
    # ========================================================
    for split in splits:
        train_dates = set(
            split.window.train_dates
        )
        validation_dates = set(
            split.window.validation_dates
        )
        test_dates = set(
            split.window.test_dates
        )
        assert not (
            train_dates
            & validation_dates
        )
        assert not (
            train_dates & test_dates
        )
        assert not (
            validation_dates
            & test_dates
        )
    print(
        "validation/split.py V392 self_test PASSED"
    )


if __name__ == "__main__":
    self_test_v392()
