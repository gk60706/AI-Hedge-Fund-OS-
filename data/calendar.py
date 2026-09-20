"""V3.6 TradingCalendar：交易日历接口。

V3.6 先提供接口；后续生产版应直接接入中国交易所实际交易日历，
并处理春节 / 国庆 / 元旦 / 清明 / 劳动节 / 临时休市等节假日。
"""

from __future__ import annotations

import pandas as pd


class TradingCalendar:
    @staticmethod
    def business_days(start_date: str, end_date: str):
        return pd.bdate_range(start=start_date, end=end_date)

    @staticmethod
    def is_trading_day(date, trading_days):
        date = pd.Timestamp(date)
        return date in set(pd.to_datetime(trading_days))


# ============================================================================
# V3.9.2 canonical TradingCalendar (step5)
#
# 设计原则：
#   - 不覆盖旧版 TradingCalendar（test_v36.py 依赖静态方法 business_days /
#     is_trading_day(date, trading_days)）
#   - 新版以 V392 后缀命名，提供完整的交易日遍历/shift/range/前后N日接口
#   - 优先支持用户传入真实交易日列表；无真实日历时 fallback 工作日
# ============================================================================

import logging as _logging_v392
from dataclasses import dataclass as _dataclass_v392
from pathlib import Path as _PathV392
from typing import (
    Iterable as _IterableV392,
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
)

logger = _logging_v392.getLogger("AIHedgeFundOS.TradingCalendarV392")


class CalendarErrorV392(Exception):
    """交易日历相关异常。"""


@_dataclass_v392(frozen=True)
class CalendarConfigV392:
    """TradingCalendarV392 配置。"""

    name: str = "CN_A_SHARE"
    # fallback 模式下的工作日频率
    fallback_frequency: str = "B"
    # 是否允许 fallback
    allow_fallback: bool = True
    # 日期格式
    date_format: str = "%Y-%m-%d"


class TradingCalendarV392:
    """中国 A 股交易日历（V3.9.2 版）。

    核心接口:
        calendar.is_trading_day(date)
        calendar.previous_trading_day(date)
        calendar.next_trading_day(date)
        calendar.shift(date, n)
        calendar.range(start, end)
    """

    def __init__(
        self,
        dates: _OptionalV392[_IterableV392] = None,
        config: _OptionalV392[CalendarConfigV392] = None,
    ) -> None:
        self.config = config or CalendarConfigV392()
        self._dates = pd.DatetimeIndex([])
        if dates is not None:
            self.set_dates(dates)

    # ----------------------------------------------------------
    # 日期标准化
    # ----------------------------------------------------------
    @staticmethod
    def normalize_date(value) -> pd.Timestamp:
        """将各种日期输入统一为 Timestamp。"""
        if value is None:
            raise CalendarErrorV392("date cannot be None")
        try:
            ts = pd.Timestamp(value)
        except Exception as exc:
            raise CalendarErrorV392(f"Invalid date: {value}") from exc
        if pd.isna(ts):
            raise CalendarErrorV392(f"Invalid date: {value}")
        return ts.normalize()

    # ----------------------------------------------------------
    # 设置交易日
    # ----------------------------------------------------------
    def set_dates(self, dates: _IterableV392) -> None:
        """设置真实交易日列表。"""
        normalized = []
        for date in dates:
            try:
                normalized.append(self.normalize_date(date))
            except CalendarErrorV392:
                logger.warning("Ignoring invalid calendar date: %s", date)
        if not normalized:
            raise CalendarErrorV392("Trading calendar cannot be empty.")
        index = pd.DatetimeIndex(normalized)
        index = index.drop_duplicates().sort_values()
        self._dates = index

    def load_from_dataframe(
        self, df: pd.DataFrame, date_column: str = "date"
    ) -> None:
        """从 DataFrame 加载交易日历。"""
        if df is None or df.empty:
            raise CalendarErrorV392("Calendar dataframe is empty.")
        if date_column not in df.columns:
            raise CalendarErrorV392(f"Missing date column: {date_column}")
        self.set_dates(df[date_column].tolist())

    def load_from_csv(
        self, path: str | _PathV392, date_column: str = "date"
    ) -> None:
        """从 CSV 加载交易日历。"""
        path = _PathV392(path)
        if not path.exists():
            raise CalendarErrorV392(f"Calendar file does not exist: {path}")
        df = pd.read_csv(path)
        self.load_from_dataframe(df, date_column=date_column)

    # ----------------------------------------------------------
    # Fallback 日历
    # ----------------------------------------------------------
    def build_fallback(self, start_date, end_date) -> None:
        """创建 fallback 工作日日历（非生产级）。"""
        if not self.config.allow_fallback:
            raise CalendarErrorV392("Fallback trading calendar is disabled.")
        start = self.normalize_date(start_date)
        end = self.normalize_date(end_date)
        if start > end:
            raise CalendarErrorV392("start_date must be <= end_date")
        dates = pd.date_range(
            start=start, end=end, freq=self.config.fallback_frequency
        )
        self._dates = dates
        logger.warning(
            "Using fallback business-day calendar. "
            "This is NOT a production-grade A-share calendar."
        )

    # ----------------------------------------------------------
    # 访问器
    # ----------------------------------------------------------
    @property
    def dates(self) -> pd.DatetimeIndex:
        return self._dates

    @property
    def empty(self) -> bool:
        return len(self._dates) == 0

    @property
    def first_date(self) -> _OptionalV392[pd.Timestamp]:
        if self.empty:
            return None
        return self._dates[0]

    @property
    def last_date(self) -> _OptionalV392[pd.Timestamp]:
        if self.empty:
            return None
        return self._dates[-1]

    def __len__(self) -> int:
        return len(self._dates)

    # ----------------------------------------------------------
    # 交易日判断
    # ----------------------------------------------------------
    def is_trading_day(self, date) -> bool:
        """判断某一天是否为交易日。"""
        ts = self.normalize_date(date)
        if self.empty:
            if not self.config.allow_fallback:
                raise CalendarErrorV392("Trading calendar is empty.")
            return ts.weekday() < 5
        return ts in self._dates

    # ----------------------------------------------------------
    # 最近交易日
    # ----------------------------------------------------------
    def previous_trading_day(
        self, date, include_current: bool = False
    ) -> pd.Timestamp:
        """获取指定日期之前的交易日。"""
        ts = self.normalize_date(date)
        if self.empty:
            return self._fallback_shift(
                ts, -1 if not include_current else 0
            )
        if include_current:
            pos = self._search_position(ts, side="left")
            if pos < len(self._dates):
                return self._dates[pos]
        pos = self._search_position(ts, side="left") - 1
        if pos < 0:
            raise CalendarErrorV392(
                f"No previous trading day available for {ts.date()}"
            )
        return self._dates[pos]

    def next_trading_day(
        self, date, include_current: bool = False
    ) -> pd.Timestamp:
        """获取指定日期之后的交易日。"""
        ts = self.normalize_date(date)
        if self.empty:
            return self._fallback_shift(
                ts, 1 if not include_current else 0
            )
        if include_current:
            pos = self._search_position(ts, side="left")
            if (
                pos < len(self._dates)
                and self._dates[pos] == ts
            ):
                return ts
        pos = self._search_position(ts, side="right")
        if pos >= len(self._dates):
            raise CalendarErrorV392(
                f"No next trading day available for {ts.date()}"
            )
        return self._dates[pos]

    # ----------------------------------------------------------
    # 日期偏移
    # ----------------------------------------------------------
    def shift(self, date, periods: int) -> pd.Timestamp:
        """按交易日移动。"""
        ts = self.normalize_date(date)
        if self.empty:
            return self._fallback_shift(ts, periods)
        if ts in self._dates:
            pos = self._dates.get_loc(ts)
        else:
            if periods >= 0:
                pos = self._search_position(ts, side="left")
            else:
                pos = self._search_position(ts, side="right") - 1
        target_pos = pos + periods
        if target_pos < 0 or target_pos >= len(self._dates):
            raise CalendarErrorV392(
                f"Trading day shift out of range: "
                f"date={ts.date()}, periods={periods}"
            )
        return self._dates[target_pos]

    # ----------------------------------------------------------
    # 日期区间
    # ----------------------------------------------------------
    def range(
        self, start_date, end_date, inclusive: str = "both"
    ) -> pd.DatetimeIndex:
        """获取交易日区间。inclusive: both/left/right/neither。"""
        start = self.normalize_date(start_date)
        end = self.normalize_date(end_date)
        if start > end:
            raise CalendarErrorV392("start_date must be <= end_date")
        if self.empty:
            if not self.config.allow_fallback:
                raise CalendarErrorV392("Trading calendar is empty.")
            return pd.date_range(
                start=start, end=end, freq=self.config.fallback_frequency
            )
        mask = (self._dates >= start) & (self._dates <= end)
        result = self._dates[mask]
        if inclusive != "both":
            if inclusive in {"left", "neither"}:
                result = result[result > start]
            if inclusive in {"right", "neither"}:
                result = result[result < end]
        return result

    # ----------------------------------------------------------
    # 搜索位置
    # ----------------------------------------------------------
    def _search_position(self, ts: pd.Timestamp, side: str = "left") -> int:
        """返回插入位置。"""
        if side not in {"left", "right"}:
            raise ValueError("side must be 'left' or 'right'")
        return int(self._dates.searchsorted(ts, side=side))

    # ----------------------------------------------------------
    # fallback shift
    # ----------------------------------------------------------
    @staticmethod
    def _fallback_shift(
        date: pd.Timestamp, periods: int
    ) -> pd.Timestamp:
        """fallback 模式下的交易日移动（仅跳过周末）。"""
        if periods == 0:
            return date
        step = 1 if periods > 0 else -1
        current = date
        remaining = abs(periods)
        while remaining > 0:
            current = current + pd.Timedelta(days=step)
            if current.weekday() < 5:
                remaining -= 1
        return current

    # ----------------------------------------------------------
    # 最近交易日
    # ----------------------------------------------------------
    def nearest_trading_day(
        self, date, direction: str = "previous"
    ) -> pd.Timestamp:
        """获取最近交易日。direction: previous/next。"""
        ts = self.normalize_date(date)
        if self.empty:
            if direction == "previous":
                return self.previous_trading_day(ts, include_current=True)
            if direction == "next":
                return self.next_trading_day(ts, include_current=True)
            raise CalendarErrorV392("direction must be previous or next")
        if ts in self._dates:
            return ts
        if direction == "previous":
            return self.previous_trading_day(ts, include_current=False)
        if direction == "next":
            return self.next_trading_day(ts, include_current=False)
        raise CalendarErrorV392("direction must be previous or next")

    # ----------------------------------------------------------
    # 前后 N 个交易日
    # ----------------------------------------------------------
    def previous_n_days(self, date, n: int) -> pd.DatetimeIndex:
        """获取前 N 个交易日（不包含当前日期）。"""
        if n <= 0:
            raise CalendarErrorV392("n must be positive")
        current = self.normalize_date(date)
        if self.empty:
            dates = []
            for i in range(1, n + 1):
                dates.append(self._fallback_shift(current, -i))
            return pd.DatetimeIndex(sorted(dates))
        pos = self._search_position(current, side="left")
        end_pos = pos
        start_pos = max(0, end_pos - n)
        return self._dates[start_pos:end_pos]

    def next_n_days(self, date, n: int) -> pd.DatetimeIndex:
        """获取后 N 个交易日（不包含当前日期）。"""
        if n <= 0:
            raise CalendarErrorV392("n must be positive")
        current = self.normalize_date(date)
        if self.empty:
            dates = []
            for i in range(1, n + 1):
                dates.append(self._fallback_shift(current, i))
            return pd.DatetimeIndex(dates)
        pos = self._search_position(current, side="right")
        return self._dates[pos : pos + n]

    # ----------------------------------------------------------
    # 覆盖判断
    # ----------------------------------------------------------
    def covers(self, start_date, end_date) -> bool:
        """判断当前交易日历是否覆盖整个区间。"""
        if self.empty:
            return False
        start = self.normalize_date(start_date)
        end = self.normalize_date(end_date)
        return self.first_date <= start and self.last_date >= end

    # ----------------------------------------------------------
    # 统计信息
    # ----------------------------------------------------------
    def info(self) -> dict:
        """返回交易日历信息。"""
        return {
            "name": self.config.name,
            "count": len(self._dates),
            "first_date": (
                self.first_date.strftime(self.config.date_format)
                if self.first_date is not None
                else None
            ),
            "last_date": (
                self.last_date.strftime(self.config.date_format)
                if self.last_date is not None
                else None
            ),
            "is_empty": self.empty,
            "fallback_allowed": self.config.allow_fallback,
        }


# ============================================================================
# 默认日历 & 便捷函数（V3.9.2 新增；旧版无同名函数，不冲突）
# ============================================================================


def create_default_calendar(
    start_date: str = "2010-01-01",
    end_date: str = "2035-12-31",
) -> TradingCalendarV392:
    """创建默认交易日历（V3.9.2 原型阶段使用 fallback 工作日）。"""
    calendar = TradingCalendarV392()
    calendar.build_fallback(start_date=start_date, end_date=end_date)
    return calendar


def is_trading_day_v392(
    date,
    calendar: _OptionalV392[TradingCalendarV392] = None,
) -> bool:
    """判断交易日（V3.9.2 模块级便捷函数）。"""
    if calendar is None:
        year = pd.Timestamp(date).year
        calendar = create_default_calendar(
            start_date=f"{year}-01-01",
            end_date=f"{year}-12-31",
        )
    return calendar.is_trading_day(date)


def shift_trading_day_v392(
    date,
    periods: int,
    calendar: _OptionalV392[TradingCalendarV392] = None,
) -> pd.Timestamp:
    """交易日偏移（V3.9.2 模块级便捷函数）。"""
    if calendar is None:
        year = pd.Timestamp(date).year
        calendar = create_default_calendar(
            start_date=f"{year - 2}-01-01",
            end_date=f"{year + 2}-12-31",
        )
    return calendar.shift(date, periods)


def get_trading_days_v392(
    start_date,
    end_date,
    calendar: _OptionalV392[TradingCalendarV392] = None,
) -> pd.DatetimeIndex:
    """获取交易日列表（V3.9.2 模块级便捷函数）。"""
    if calendar is None:
        calendar = create_default_calendar(
            start_date=start_date, end_date=end_date
        )
    return calendar.range(start_date, end_date)
