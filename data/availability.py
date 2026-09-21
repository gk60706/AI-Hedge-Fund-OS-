from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import pandas as pd


@dataclass(frozen=True)
class DataAvailability:
    field: str
    period_end: date
    publish_date: date
    available_date: date


class AvailabilityChecker:
    def is_available(self, item: DataAvailability, as_of_date: date,) -> bool:
        return (item.available_date <= as_of_date)

    def assert_available(self, item: DataAvailability, as_of_date: date,):
        if not self.is_available(item, as_of_date,):
            raise ValueError(
                f"未来数据泄漏: "
                f"'{item.field}'"
                f"available={item.available_date}"
                f"as_of={as_of_date}"
            )


# ============================================================================
# V3.9.1 unified research engine - availability check
# ============================================================================


def validate_availability(
    panel: pd.DataFrame,
    min_observations: int = 120,
):
    counts = panel.groupby("code").size()
    return counts[counts >= min_observations]


# ============================================================================
# V3.9.2 Data Availability Engine (step8)
#
# 设计原则：
#   - 不覆盖旧版 DataAvailability / AvailabilityChecker / validate_availability
#     （tests/test_v37_v38.py 仍依赖旧版）
#   - 以 DataFrame 为中心，统一解析 available_date 的来源优先级：
#       explicit available_date > announcement_date > event_date > report_period
#   - report_period fallback 默认关闭（强烈建议 False），
#     因为 report_period ≠ 市场知道日期，会引入 look-ahead bias
#   - available_date 无法可靠确定时，宁可拒绝使用，也不偷偷制造未来数据
# ============================================================================

import logging as _logging_v392
from dataclasses import dataclass as _dataclass_v392
from enum import Enum as _Enum_v392
from typing import (
    Iterable as _IterableV392,
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
)

import numpy as _np_v392

logger = _logging_v392.getLogger(
    "AIHedgeFundOS.DataAvailabilityEngineV392"
)


class AvailabilityError(Exception):
    """数据可获得性异常。"""


# ----------------------------------------------------------------------------
# AvailabilityType
# ----------------------------------------------------------------------------
class AvailabilityTypeV392(str, _Enum_v392):
    """数据可获得时间的来源类型。"""

    EXPLICIT_AVAILABLE_DATE = "explicit_available_date"
    ANNOUNCEMENT_DATE = "announcement_date"
    EVENT_DATE = "event_date"
    REPORT_PERIOD = "report_period"
    UNKNOWN = "unknown"


# ----------------------------------------------------------------------------
# AvailabilityConfig
# ----------------------------------------------------------------------------
@_dataclass_v392(frozen=True)
class AvailabilityConfigV392:
    """Data Availability 配置。"""

    code_column: str = "code"
    date_column: str = "date"
    report_period_column: str = "report_period"
    event_date_column: str = "event_date"
    announcement_date_column: str = "announcement_date"
    available_date_column: str = "available_date"
    effective_date_column: str = "effective_date"

    # fallback 开关
    allow_announcement_fallback: bool = True
    allow_event_fallback: bool = False
    # 强烈建议 False：report_period ≠ 市场知道日期
    allow_report_period_fallback: bool = False

    strict: bool = True
    keep_unknown: bool = False
    enforce_non_future: bool = True


# ----------------------------------------------------------------------------
# AvailabilityRecord
# ----------------------------------------------------------------------------
@_dataclass_v392
class AvailabilityRecordV392:
    """单条数据的可获得性信息。"""

    code: str
    report_period: _OptionalV392[pd.Timestamp] = None
    event_date: _OptionalV392[pd.Timestamp] = None
    announcement_date: _OptionalV392[pd.Timestamp] = None
    available_date: _OptionalV392[pd.Timestamp] = None
    effective_date: _OptionalV392[pd.Timestamp] = None
    availability_type: AvailabilityTypeV392 = (
        AvailabilityTypeV392.UNKNOWN
    )
    confidence: str = "unknown"

    def is_known(self) -> bool:
        return self.available_date is not None


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
def normalize_date_v392(value) -> _OptionalV392[pd.Timestamp]:
    """标准化日期。None / NaT 返回 None。"""
    if value is None:
        return None
    if isinstance(value, float) and _np_v392.isnan(value):
        return None
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.normalize()


def normalize_code_v392(code) -> str:
    """标准化股票代码，输出 6 位数字 + .SH/.SZ/.BJ。"""
    if code is None:
        return ""
    value = (
        str(code)
        .strip()
        .upper()
        .replace("_", ".")
        .replace("-", ".")
    )
    if not value:
        return ""
    if "." in value:
        parts = value.split(".")
        if len(parts) == 2:
            left, right = parts
            if left in {"SH", "SZ", "BJ"}:
                code_part = right
                exchange = left
            elif right in {"SH", "SZ", "BJ"}:
                code_part = left
                exchange = right
            else:
                code_part = left
                exchange = ""
        else:
            code_part = parts[0]
            exchange = ""
    else:
        code_part = value
        exchange = ""
    code_part = "".join(c for c in code_part if c.isdigit())
    if not code_part:
        return ""
    code_part = code_part.zfill(6)
    if not exchange:
        if code_part.startswith(("60", "68", "69")):
            exchange = "SH"
        elif code_part.startswith(("00", "30", "31")):
            exchange = "SZ"
        elif code_part.startswith(("43", "83", "87", "88", "92")):
            exchange = "BJ"
    if exchange:
        return f"{code_part}.{exchange}"
    return code_part


# ----------------------------------------------------------------------------
# DataAvailabilityEngine
# ----------------------------------------------------------------------------
class DataAvailabilityEngineV392:
    """数据可获得性引擎。

    核心：resolve(row) -> AvailabilityRecordV392
    返回 available_date / availability_type / confidence。
    """

    def __init__(
        self, config: _OptionalV392[AvailabilityConfigV392] = None
    ) -> None:
        self.config = config or AvailabilityConfigV392()

    # ---------------- 解析单条记录 ----------------
    def resolve(self, row: pd.Series) -> AvailabilityRecordV392:
        """按优先级解析一条数据的 available_date。

        优先级：
          1. explicit available_date (high confidence)
          2. announcement_date (medium)
          3. event_date (low，默认关闭)
          4. report_period (very_low，默认关闭，会 warning)
          5. unknown
        """
        code = normalize_code_v392(
            row.get(self.config.code_column)
        )
        report_period = normalize_date_v392(
            row.get(self.config.report_period_column)
        )
        event_date = normalize_date_v392(
            row.get(self.config.event_date_column)
        )
        announcement_date = normalize_date_v392(
            row.get(self.config.announcement_date_column)
        )
        explicit_available = normalize_date_v392(
            row.get(self.config.available_date_column)
        )
        effective_date = normalize_date_v392(
            row.get(self.config.effective_date_column)
        )

        def _make(avail, atype, conf):
            return AvailabilityRecordV392(
                code=code,
                report_period=report_period,
                event_date=event_date,
                announcement_date=announcement_date,
                available_date=avail,
                effective_date=effective_date,
                availability_type=atype,
                confidence=conf,
            )

        # 1. explicit available_date
        if explicit_available is not None:
            return _make(
                explicit_available,
                AvailabilityTypeV392.EXPLICIT_AVAILABLE_DATE,
                "high",
            )
        # 2. announcement_date
        if (
            self.config.allow_announcement_fallback
            and announcement_date is not None
        ):
            return _make(
                announcement_date,
                AvailabilityTypeV392.ANNOUNCEMENT_DATE,
                "medium",
            )
        # 3. event_date
        if (
            self.config.allow_event_fallback
            and event_date is not None
        ):
            return _make(
                event_date,
                AvailabilityTypeV392.EVENT_DATE,
                "low",
            )
        # 4. report_period（默认关闭，开启会 warning）
        if (
            self.config.allow_report_period_fallback
            and report_period is not None
        ):
            logger.warning(
                "Using report_period as available_date for %s. "
                "This may introduce look-ahead bias.",
                code,
            )
            return _make(
                report_period,
                AvailabilityTypeV392.REPORT_PERIOD,
                "very_low",
            )
        # 5. unknown
        return _make(
            None,
            AvailabilityTypeV392.UNKNOWN,
            "unknown",
        )

    # ---------------- DataFrame 准备 ----------------
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """为 DataFrame 建立统一 available_date。"""
        if df is None:
            raise AvailabilityError("DataFrame cannot be None.")
        if df.empty:
            return df.copy()
        result = df.copy()

        # code 标准化
        if self.config.code_column in result.columns:
            result[self.config.code_column] = result[
                self.config.code_column
            ].map(normalize_code_v392)

        # 日期字段统一 to_datetime
        date_columns = [
            self.config.date_column,
            self.config.report_period_column,
            self.config.event_date_column,
            self.config.announcement_date_column,
            self.config.available_date_column,
            self.config.effective_date_column,
        ]
        for column in date_columns:
            if column in result.columns:
                result[column] = (
                    pd.to_datetime(result[column], errors="coerce")
                    .dt.normalize()
                )

        # 逐行 resolve
        records = []
        for _, row in result.iterrows():
            record = self.resolve(row)
            records.append(
                {
                    "_resolved_available_date": record.available_date,
                    "_availability_type": record.availability_type.value,
                    "_availability_confidence": record.confidence,
                }
            )
        resolved = pd.DataFrame(records, index=result.index)
        result = pd.concat([result, resolved], axis=1)

        # 原始 available_date 缺失则用 resolve 结果填充
        available_col = self.config.available_date_column
        resolved_col = "_resolved_available_date"
        if available_col not in result.columns:
            result[available_col] = result[resolved_col]
        else:
            result[available_col] = result[available_col].fillna(
                result[resolved_col]
            )
        return result

    # ---------------- 可获得性判断 ----------------
    def is_available(
        self, row: pd.Series, as_of_date
    ) -> bool:
        """判断数据在某个研究日期是否可用。"""
        as_of = normalize_date_v392(as_of_date)
        if as_of is None:
            raise AvailabilityError("Invalid as_of_date.")
        record = self.resolve(row)
        if record.available_date is None:
            return bool(self.config.keep_unknown)
        if self.config.enforce_non_future:
            return record.available_date <= as_of
        return True

    # ---------------- 过滤 ----------------
    def filter_as_of(
        self, df: pd.DataFrame, as_of_date
    ) -> pd.DataFrame:
        """返回截至 as_of_date 可以使用的数据。"""
        result = self.prepare(df)
        if result.empty:
            return result
        as_of = normalize_date_v392(as_of_date)
        available_col = self.config.available_date_column
        available = (
            pd.to_datetime(result[available_col], errors="coerce")
            .dt.normalize()
        )
        valid = available.notna() & (available <= as_of)
        if self.config.keep_unknown:
            valid = valid | available.isna()
        return (
            result.loc[valid].copy().reset_index(drop=True)
        )

    # ---------------- Future / Unknown mask ----------------
    def future_mask(
        self, df: pd.DataFrame, as_of_date
    ) -> pd.Series:
        result = self.prepare(df)
        as_of = normalize_date_v392(as_of_date)
        available = (
            pd.to_datetime(
                result[self.config.available_date_column],
                errors="coerce",
            )
            .dt.normalize()
        )
        return available.notna() & (available > as_of)

    def unknown_mask(self, df: pd.DataFrame) -> pd.Series:
        result = self.prepare(df)
        available = (
            pd.to_datetime(
                result[self.config.available_date_column],
                errors="coerce",
            )
            .dt.normalize()
        )
        return available.isna()

    # ---------------- 最新可用数据 ----------------
    def latest(
        self, df: pd.DataFrame, as_of_date
    ) -> pd.DataFrame:
        """每只股票截至指定日期最新可用记录。"""
        result = self.filter_as_of(df, as_of_date)
        if result.empty:
            return result
        code_col = self.config.code_column
        available_col = self.config.available_date_column
        result = result.sort_values([code_col, available_col])
        return (
            result.groupby(code_col, as_index=False, sort=False)
            .tail(1)
            .reset_index(drop=True)
        )

    # ---------------- 审计 ----------------
    def audit(self, df: pd.DataFrame, as_of_date) -> dict:
        """审计数据的可获得性。"""
        result = self.prepare(df)
        total = len(result)
        if total == 0:
            return {
                "as_of_date": str(as_of_date),
                "total_rows": 0,
                "available_rows": 0,
                "future_rows": 0,
                "unknown_rows": 0,
                "available_ratio": 0.0,
                "future_ratio": 0.0,
                "unknown_ratio": 0.0,
                "passed": True,
            }
        future = self.future_mask(result, as_of_date)
        unknown = self.unknown_mask(result)
        available = ~future & ~unknown
        future_count = int(future.sum())
        unknown_count = int(unknown.sum())
        available_count = int(available.sum())
        passed = (
            future_count == 0
            and (
                self.config.keep_unknown or unknown_count == 0
            )
        )
        return {
            "as_of_date": normalize_date_v392(as_of_date).strftime(
                "%Y-%m-%d"
            ),
            "total_rows": total,
            "available_rows": available_count,
            "future_rows": future_count,
            "unknown_rows": unknown_count,
            "available_ratio": available_count / total,
            "future_ratio": future_count / total,
            "unknown_ratio": unknown_count / total,
            "passed": passed,
        }

    # ---------------- 日期关系一致性检查 ----------------
    def consistency_check(self, df: pd.DataFrame) -> pd.DataFrame:
        """检查日期逻辑是否存在明显异常（warning 级别，不抛错）。"""
        result = self.prepare(df)
        if result.empty:
            return pd.DataFrame()
        rows = []
        for index, row in result.iterrows():
            report_period = normalize_date_v392(
                row.get(self.config.report_period_column)
            )
            announcement_date = normalize_date_v392(
                row.get(self.config.announcement_date_column)
            )
            available_date = normalize_date_v392(
                row.get(self.config.available_date_column)
            )
            effective_date = normalize_date_v392(
                row.get(self.config.effective_date_column)
            )
            warnings = []
            if (
                report_period is not None
                and announcement_date is not None
                and announcement_date < report_period
            ):
                warnings.append("announcement_before_report_period")
            if (
                announcement_date is not None
                and available_date is not None
                and available_date < announcement_date
            ):
                warnings.append("available_before_announcement")
            if (
                report_period is not None
                and effective_date is not None
                and effective_date < report_period
            ):
                warnings.append("effective_before_report_period")
            rows.append(
                {
                    "index": index,
                    "code": row.get(self.config.code_column),
                    "warnings": warnings,
                    "has_warning": bool(warnings),
                }
            )
        return pd.DataFrame(rows)

    # ---------------- 构建 Availability Panel ----------------
    def build_panel(
        self,
        df: pd.DataFrame,
        research_dates: _SequenceV392,
    ) -> pd.DataFrame:
        """构建 research_date × security 的 PIT Availability Panel。"""
        result = self.prepare(df)
        if result.empty:
            return result
        rows = []
        for research_date in research_dates:
            as_of = normalize_date_v392(research_date)
            available = self.filter_as_of(result, as_of)
            if available.empty:
                continue
            available = available.copy()
            available["as_of_date"] = as_of
            rows.append(available)
        if not rows:
            columns = list(result.columns)
            if "as_of_date" not in columns:
                columns.append("as_of_date")
            return pd.DataFrame(columns=columns)
        return (
            pd.concat(rows, ignore_index=True)
            .sort_values(
                [
                    "as_of_date",
                    self.config.code_column,
                    self.config.available_date_column,
                ]
            )
            .reset_index(drop=True)
        )


# ----------------------------------------------------------------------------
# 模块级便捷函数
# ----------------------------------------------------------------------------
def prepare_availability_v392(
    df: pd.DataFrame,
    config: _OptionalV392[AvailabilityConfigV392] = None,
) -> pd.DataFrame:
    """统一处理 available_date。"""
    engine = DataAvailabilityEngineV392(config=config)
    return engine.prepare(df)


def filter_available_v392(
    df: pd.DataFrame,
    as_of_date,
    config: _OptionalV392[AvailabilityConfigV392] = None,
) -> pd.DataFrame:
    """截至指定日期过滤数据。"""
    engine = DataAvailabilityEngineV392(config=config)
    return engine.filter_as_of(df, as_of_date)


def audit_availability_v392(
    df: pd.DataFrame,
    as_of_date,
    config: _OptionalV392[AvailabilityConfigV392] = None,
) -> dict:
    """审计数据可获得性。"""
    engine = DataAvailabilityEngineV392(config=config)
    return engine.audit(df, as_of_date)
