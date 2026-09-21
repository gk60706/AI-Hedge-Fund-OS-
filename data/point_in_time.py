from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PITRecord:
    code: str
    period_end: date
    value: Any
    publish_date: date
    available_date: date | None = None

    def effective_date(self) -> date:
        if self.available_date is not None:
            return self.available_date
        return self.publish_date


class PointInTimeStore:
    def __init__(self):
        self.records: list[PITRecord] = []

    def add(self, record: PITRecord,):
        self.records.append(record)

    def query(self, code: str, as_of_date: date,):
        candidates = [
            record
            for record in self.records
            if record.code == code
            and record.effective_date() <= as_of_date
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda x: (
                x.period_end,
                x.effective_date(),
            )
        )
        return candidates[-1]

    def query_many(self, code: str, as_of_date: date,):
        return [
            record
            for record in self.records
            if record.code == code
            and record.effective_date() <= as_of_date
        ]


# ============================================================================
# V3.9.1 unified research engine - DataFrame point-in-time store
# ============================================================================

PIT_REQUIRED_COLUMNS = [
    "code",
    "field",
    "period_end",
    "value",
    "publish_date",
    "available_date",
]


class V391PointInTimeStore:
    def __init__(self, records=None):
        if records is None:
            self.records = pd.DataFrame(columns=PIT_REQUIRED_COLUMNS)
        else:
            self.records = records.copy()

    def add(self, frame: pd.DataFrame) -> None:
        missing = [
            c for c in PIT_REQUIRED_COLUMNS if c not in frame.columns
        ]
        if missing:
            raise ValueError(f"PIT DataFrame 缺少字段: {missing}")
        self.records = pd.concat(
            [self.records, frame[PIT_REQUIRED_COLUMNS]],
            ignore_index=True,
        )

    def query(self, code: str, field: str, as_of):
        candidates = self.records[
            (self.records["code"] == code)
            & (self.records["field"] == field)
            & (
                pd.to_datetime(self.records["available_date"])
                <= pd.Timestamp(as_of)
            )
        ]
        if candidates.empty:
            return None
        candidates = candidates.sort_values(["period_end", "available_date"])
        return float(candidates.iloc[-1]["value"])


# ============================================================================
# V3.9.2 Point-in-Time Engine (step7)
#
# 设计原则：
#   - 不覆盖旧版 PITRecord / PointInTimeStore / V391PointInTimeStore
#     （main_v37.py、tests/test_pit.py、tests/test_v37_v38.py 仍依赖旧版）
#   - 新版以 DataFrame 为中心，处理财务数据 → 行情合并的 PIT 防泄漏
#   - 核心规则：available_date <= as_of_date 才可用
#   - 没有真实 announcement_date / available_date 时，宁可拒绝使用，
#     也不偷偷制造未来数据
# ============================================================================

import logging as _logging_v392
from dataclasses import dataclass as _dataclass_v392
from typing import (
    Iterable as _IterableV392,
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
)

import numpy as _np_v392

logger = _logging_v392.getLogger("AIHedgeFundOS.PointInTimeEngineV392")


class PITError(Exception):
    """Point-in-Time 数据异常。"""


@_dataclass_v392(frozen=True)
class PITConfig:
    """Point-in-Time 配置。"""

    # 研究日期字段
    date_column: str = "date"
    # 数据真正可获得日期
    available_date_column: str = "available_date"
    # 财务报告期字段
    report_period_column: str = "report_period"
    # 公告日期字段
    announcement_date_column: str = "announcement_date"
    # 股票代码
    code_column: str = "code"
    # 是否要求 PIT 字段必须存在
    require_available_date: bool = True
    # 没有 available_date 时是否允许使用 announcement_date
    allow_announcement_date_fallback: bool = True
    # 是否严格拒绝未来数据
    strict: bool = True
    # 是否删除未来数据
    drop_future_rows: bool = True
    # 是否保留无法判断 PIT 的记录
    keep_unknown_availability: bool = False


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
def normalize_date_v392(value) -> pd.Timestamp:
    """标准化日期。"""
    if value is None:
        raise PITError("Date cannot be None.")
    try:
        ts = pd.Timestamp(value)
    except Exception as exc:
        raise PITError(f"Invalid date: {value}") from exc
    if pd.isna(ts):
        raise PITError(f"Invalid date: {value}")
    return ts.normalize()


def normalize_dates_v392(values: _IterableV392) -> pd.DatetimeIndex:
    """批量日期标准化。"""
    result = []
    for value in values:
        result.append(normalize_date_v392(value))
    return pd.DatetimeIndex(result)


# ----------------------------------------------------------------------------
# PointInTimeEngine
# ----------------------------------------------------------------------------
class PointInTimeEngine:
    """Point-in-Time 数据处理引擎。

    核心接口：
        filter_as_of(df, as_of_date)
        is_available(row, as_of_date)
        latest_available(df, as_of_date)
        point_in_time_panel(df, research_dates)
    """

    def __init__(self, config: _OptionalV392[PITConfig] = None) -> None:
        self.config = config or PITConfig()

    # ---------------- 日期字段准备 ----------------
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备 PIT 数据：检查 code、解析 date/available_date/announcement_date/report_period。"""
        if df is None:
            raise PITError("DataFrame cannot be None.")
        if df.empty:
            return df.copy()
        result = df.copy()

        # code
        if self.config.code_column not in result.columns:
            raise PITError(
                f"PIT data must contain '{self.config.code_column}' column."
            )

        # date
        date_col = self.config.date_column
        if date_col in result.columns:
            result[date_col] = (
                pd.to_datetime(result[date_col], errors="coerce")
                .dt.normalize()
            )

        # available_date
        available_col = self.config.available_date_column
        if available_col not in result.columns:
            result[available_col] = pd.NaT
        else:
            result[available_col] = (
                pd.to_datetime(result[available_col], errors="coerce")
                .dt.normalize()
            )

        # announcement_date fallback
        announcement_col = self.config.announcement_date_column
        if (
            self.config.allow_announcement_date_fallback
            and announcement_col in result.columns
        ):
            announcement_dates = (
                pd.to_datetime(result[announcement_col], errors="coerce")
                .dt.normalize()
            )
            mask = (
                result[available_col].isna() & announcement_dates.notna()
            )
            result.loc[mask, available_col] = announcement_dates[mask]

        # report period
        report_col = self.config.report_period_column
        if report_col in result.columns:
            result[report_col] = (
                pd.to_datetime(result[report_col], errors="coerce")
                .dt.normalize()
            )

        return result

    # ---------------- 判断单条记录是否可用 ----------------
    def is_available(self, row: pd.Series, as_of_date) -> bool:
        """判断一条数据在指定日期是否可用：available_date <= as_of_date。"""
        as_of = normalize_date_v392(as_of_date)
        available_col = self.config.available_date_column
        if available_col not in row.index:
            if self.config.require_available_date:
                return False
            return True
        value = row[available_col]
        if pd.isna(value):
            return not self.config.require_available_date
        try:
            available = normalize_date_v392(value)
        except PITError:
            return False
        return available <= as_of

    # ---------------- 检测未来数据 ----------------
    def future_mask(self, df: pd.DataFrame, as_of_date) -> pd.Series:
        """返回未来数据 mask：True 表示 available_date > as_of_date。"""
        result = self.prepare(df)
        as_of = normalize_date_v392(as_of_date)
        available_col = self.config.available_date_column
        if available_col not in result.columns:
            return pd.Series(False, index=result.index)
        available = (
            pd.to_datetime(result[available_col], errors="coerce")
            .dt.normalize()
        )
        return available.notna() & (available > as_of)

    # ---------------- 未知 PIT 数据 ----------------
    def unknown_availability_mask(self, df: pd.DataFrame) -> pd.Series:
        """找出无法判断可获得性的数据（available_date = NaT）。"""
        result = self.prepare(df)
        available_col = self.config.available_date_column
        if available_col not in result.columns:
            return pd.Series(True, index=result.index)
        return result[available_col].isna()

    # ---------------- as-of 过滤 ----------------
    def filter_as_of(
        self, df: pd.DataFrame, as_of_date
    ) -> pd.DataFrame:
        """返回 as_of_date 当天能够获得的数据。"""
        result = self.prepare(df)
        if result.empty:
            return result
        as_of = normalize_date_v392(as_of_date)
        available_col = self.config.available_date_column

        # available_date 不存在
        if available_col not in result.columns:
            if self.config.require_available_date:
                if self.config.strict:
                    raise PITError(
                        "available_date is required for strict PIT filtering."
                    )
                return result.iloc[0:0].copy()
            return result.copy()

        available = (
            pd.to_datetime(result[available_col], errors="coerce")
            .dt.normalize()
        )
        valid_mask = available.notna() & (available <= as_of)
        unknown_mask = available.isna()
        if self.config.keep_unknown_availability:
            valid_mask = valid_mask | unknown_mask

        if self.config.strict:
            future_mask_s = (
                available.notna() & (available > as_of)
            )
            future_count = int(future_mask_s.sum())
            if future_count > 0:
                logger.debug(
                    "PIT filter removed %d future rows for %s.",
                    future_count,
                    as_of.date(),
                )
        return (
            result.loc[valid_mask].copy().reset_index(drop=True)
        )

    # ---------------- 删除未来数据 ----------------
    def remove_future_data(
        self, df: pd.DataFrame, as_of_date
    ) -> pd.DataFrame:
        """显式删除未来数据（用于数据清洗流程）。"""
        result = self.prepare(df)
        future = self.future_mask(result, as_of_date)
        if future.any():
            result = result.loc[~future].copy()
        return result.reset_index(drop=True)

    # ---------------- 最新可用记录 ----------------
    def latest_available(
        self,
        df: pd.DataFrame,
        as_of_date,
        code: _OptionalV392[str] = None,
    ) -> pd.DataFrame:
        """对每只股票取 available_date <= as_of_date 中 available_date 最大的一条。"""
        result = self.prepare(df)
        if result.empty:
            return result
        if code is not None:
            if self.config.code_column not in result.columns:
                raise PITError("Missing code column.")
            normalized_code = str(code).strip().upper()
            result = result[
                result[self.config.code_column]
                .astype(str)
                .str.upper()
                == normalized_code
            ].copy()
        available = self.filter_as_of(result, as_of_date)
        if available.empty:
            return available
        available_col = self.config.available_date_column
        code_col = self.config.code_column
        available = available.sort_values([code_col, available_col])
        latest = (
            available.groupby(code_col, as_index=False, sort=False).tail(1)
        )
        return latest.reset_index(drop=True)

    # ---------------- 批量 PIT ----------------
    def point_in_time_panel(
        self,
        df: pd.DataFrame,
        research_dates: _SequenceV392,
    ) -> pd.DataFrame:
        """构建完整 PIT Panel：每个 research_date 对应当时可获得的数据。"""
        result = self.prepare(df)
        if result.empty:
            return result
        rows = []
        research_dates_normalized = [
            normalize_date_v392(d) for d in research_dates
        ]
        for as_of in research_dates_normalized:
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

    # ---------------- PIT 合并行情数据 ----------------
    def merge_with_market_data(
        self,
        market_df: pd.DataFrame,
        fundamental_df: pd.DataFrame,
        date_column: str = "date",
        code_column: str = "code",
    ) -> pd.DataFrame:
        """将 PIT 财务数据与行情数据合并（逐股票 merge_asof backward）。"""
        if market_df is None or market_df.empty:
            return market_df.copy()
        if fundamental_df is None or fundamental_df.empty:
            return market_df.copy()
        market = market_df.copy()
        fundamental = self.prepare(fundamental_df)

        if date_column not in market.columns:
            raise PITError(f"Market data missing '{date_column}'.")
        if code_column not in market.columns:
            raise PITError(f"Market data missing '{code_column}'.")

        market[date_column] = (
            pd.to_datetime(market[date_column], errors="coerce")
            .dt.normalize()
        )
        fundamental = fundamental.rename(
            columns={
                self.config.available_date_column: "_pit_available_date"
            }
        )
        fundamental["_pit_available_date"] = (
            pd.to_datetime(
                fundamental["_pit_available_date"], errors="coerce"
            )
            .dt.normalize()
        )
        market = market.sort_values([code_column, date_column])
        fundamental = fundamental.sort_values(
            [code_column, "_pit_available_date"]
        )

        # 删除重复列（重命名为 _fundamental 后缀）
        duplicate_columns = [
            column
            for column in fundamental.columns
            if column in market.columns
            and column not in {code_column, date_column}
        ]
        if duplicate_columns:
            fundamental = fundamental.rename(
                columns={
                    column: f"{column}_fundamental"
                    for column in duplicate_columns
                }
            )

        merged_parts = []
        for code, market_group in market.groupby(
            code_column, sort=False
        ):
            market_group = (
                market_group.sort_values(date_column).copy()
            )
            fundamental_group = (
                fundamental[
                    fundamental[code_column].astype(str).str.upper()
                    == str(code).upper()
                ]
                .sort_values("_pit_available_date")
                .copy()
            )
            if fundamental_group.empty:
                merged_parts.append(market_group)
                continue
            merged = pd.merge_asof(
                market_group,
                fundamental_group,
                left_on=date_column,
                right_on="_pit_available_date",
                direction="backward",
                allow_exact_matches=True,
            )
            merged_parts.append(merged)

        if not merged_parts:
            return market.copy()
        return (
            pd.concat(merged_parts, ignore_index=True)
            .sort_values([date_column, code_column])
            .reset_index(drop=True)
        )

    # ---------------- 检查 PIT ----------------
    def audit(self, df: pd.DataFrame, as_of_date) -> dict:
        """对 PIT 数据进行审计。"""
        result = self.prepare(df)
        as_of = normalize_date_v392(as_of_date)
        if result.empty:
            return {
                "as_of_date": as_of.strftime("%Y-%m-%d"),
                "rows": 0,
                "future_rows": 0,
                "unknown_rows": 0,
                "valid_rows": 0,
                "future_ratio": 0.0,
                "unknown_ratio": 0.0,
                "passed": True,
            }
        future = self.future_mask(result, as_of)
        unknown = self.unknown_availability_mask(result)
        valid = ~future & ~unknown
        total = len(result)
        future_count = int(future.sum())
        unknown_count = int(unknown.sum())
        valid_count = int(valid.sum())
        return {
            "as_of_date": as_of.strftime("%Y-%m-%d"),
            "rows": total,
            "future_rows": future_count,
            "unknown_rows": unknown_count,
            "valid_rows": valid_count,
            "future_ratio": (
                future_count / total if total > 0 else 0.0
            ),
            "unknown_ratio": (
                unknown_count / total if total > 0 else 0.0
            ),
            "passed": (
                future_count == 0
                and (
                    self.config.keep_unknown_availability
                    or unknown_count == 0
                    or not self.config.require_available_date
                )
            ),
        }


# ----------------------------------------------------------------------------
# 模块级便捷函数
# ----------------------------------------------------------------------------
def filter_pit_v392(
    df: pd.DataFrame,
    as_of_date,
    config: _OptionalV392[PITConfig] = None,
) -> pd.DataFrame:
    """便捷 PIT 过滤。"""
    engine = PointInTimeEngine(config=config)
    return engine.filter_as_of(df, as_of_date)


def latest_pit_v392(
    df: pd.DataFrame,
    as_of_date,
    config: _OptionalV392[PITConfig] = None,
) -> pd.DataFrame:
    """获取截至某日期最新可用数据。"""
    engine = PointInTimeEngine(config=config)
    return engine.latest_available(df, as_of_date)


def audit_pit_v392(
    df: pd.DataFrame,
    as_of_date,
    config: _OptionalV392[PITConfig] = None,
) -> dict:
    """PIT 审计。"""
    engine = PointInTimeEngine(config=config)
    return engine.audit(df, as_of_date)
