from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import pandas as pd


@dataclass(frozen=True)
class SecurityLifecycle:
    code: str
    ipo_date: date
    delist_date: date | None = None
    name: str = ""


class HistoricalUniverse:
    def __init__(self):
        self.securities: dict[str, SecurityLifecycle] = {}

    def add(self, security: SecurityLifecycle,):
        self.securities[security.code] = security

    def is_active(self, code: str, as_of_date: date,) -> bool:
        security = self.securities.get(code)
        if security is None:
            return False
        if as_of_date < security.ipo_date:
            return False
        if (
            security.delist_date is not None
            and as_of_date >= security.delist_date
        ):
            return False
        return True

    def active_codes(self, as_of_date: date,) -> list[str]:
        return [
            code
            for code in self.securities
            if self.is_active(code, as_of_date,)
        ]


# ============================================================================
# V3.9.1 unified research engine - universe filter
# ============================================================================


class HistoricalUniverseV391:
    def __init__(self, codes):
        self.codes = set(codes)

    def filter(self, panel: pd.DataFrame) -> pd.DataFrame:
        return panel[panel["code"].isin(self.codes)].copy()


# ============================================================================
# V3.9.2 HistoricalUniverse (step6)
#
# 设计原则：
#   - 不覆盖旧版 HistoricalUniverse / SecurityLifecycle / HistoricalUniverseV391
#     （validation/survivorship.py、validation/audit.py、tests/test_v37_v38.py、
#      main_v37.py 仍依赖旧版接口）
#   - 新版以 V392 后缀命名，解决 Survivorship Bias：
#     上市日期 / 退市日期 / ST / *ST / 停牌 / 指定日期可交易股票池
#   - 核心原则：Universe(t) 只能包含 t 时刻已上市、未退市、满足研究条件的股票
# ============================================================================

import logging as _logging_v392
from dataclasses import dataclass as _dataclass_v392
from pathlib import Path as _PathV392
from typing import (
    Iterable as _IterableV392,
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
)

logger = _logging_v392.getLogger("AIHedgeFundOS.HistoricalUniverseV392")


class UniverseErrorV392(Exception):
    """HistoricalUniverseV392 相关异常。"""


@_dataclass_v392(frozen=True)
class UniverseConfigV392:
    """HistoricalUniverseV392 配置。"""

    exclude_st: bool = True
    exclude_star_st: bool = True
    exclude_suspended: bool = True
    require_listed: bool = True
    exclude_delisted: bool = True
    only_common_stock: bool = True
    include_listing_day: bool = True


@_dataclass_v392
class SecurityInfoV392:
    """单只股票的历史元数据。"""

    code: str
    name: str = ""
    exchange: str = ""
    list_date: _OptionalV392[pd.Timestamp] = None
    delist_date: _OptionalV392[pd.Timestamp] = None
    is_st: bool = False
    is_star_st: bool = False
    is_suspended: bool = False
    security_type: str = "stock"
    industry: _OptionalV392[str] = None
    market_cap: _OptionalV392[float] = None

    def normalize(self) -> "SecurityInfoV392":
        self.code = normalize_stock_code_v392(self.code)
        if self.list_date is not None:
            self.list_date = normalize_date_v392(self.list_date)
        if self.delist_date is not None:
            self.delist_date = normalize_date_v392(self.delist_date)
        return self


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------
def normalize_date_v392(value) -> pd.Timestamp:
    """标准化日期。"""
    if value is None:
        raise UniverseErrorV392("Date cannot be None.")
    try:
        ts = pd.Timestamp(value)
    except Exception as exc:
        raise UniverseErrorV392(f"Invalid date: {value}") from exc
    if pd.isna(ts):
        raise UniverseErrorV392(f"Invalid date: {value}")
    return ts.normalize()


def normalize_stock_code_v392(code) -> str:
    """标准化股票代码（支持 600519 / 600519.SH / SH.600519 / sz000001 / 000001.SZ）。"""
    if code is None:
        raise UniverseErrorV392("Stock code cannot be None.")
    value = str(code).strip().upper()
    if not value:
        raise UniverseErrorV392("Stock code cannot be empty.")
    value = (
        value.replace(" ", "").replace("_", ".").replace("-", ".")
    )
    if "." in value:
        parts = value.split(".")
        if len(parts) == 2:
            left, right = parts
            if left in {"SH", "SZ", "BJ"}:
                code_part, exchange = right, left
            elif right in {"SH", "SZ", "BJ"}:
                code_part, exchange = left, right
            else:
                code_part, exchange = left, ""
        else:
            code_part, exchange = parts[0], ""
    else:
        code_part, exchange = value, ""
    code_part = "".join(c for c in code_part if c.isdigit())
    if not code_part:
        raise UniverseErrorV392(f"Invalid stock code: {code}")
    code_part = code_part.zfill(6)
    if not exchange:
        if code_part.startswith(("60", "68", "69")):
            exchange = "SH"
        elif code_part.startswith(("00", "30", "31")):
            exchange = "SZ"
        elif code_part.startswith(("43", "83", "87", "88", "92")):
            exchange = "BJ"
        else:
            exchange = ""
    if exchange:
        return f"{code_part}.{exchange}"
    return code_part


def normalize_codes_v392(codes: _IterableV392) -> list[str]:
    """批量标准化股票代码。"""
    result = []
    for code in codes:
        try:
            normalized = normalize_stock_code_v392(code)
        except UniverseErrorV392:
            logger.warning("Ignoring invalid stock code: %s", code)
            continue
        if normalized not in result:
            result.append(normalized)
    return result


# ----------------------------------------------------------------------------
# HistoricalUniverseV392
# ----------------------------------------------------------------------------
class HistoricalUniverseV392:
    """历史股票池（V3.9.2 版）。

    key: 标准化股票代码；value: SecurityInfoV392
    """

    def __init__(
        self,
        securities: _OptionalV392[_IterableV392[SecurityInfoV392]] = None,
        config: _OptionalV392[UniverseConfigV392] = None,
    ) -> None:
        self.config = config or UniverseConfigV392()
        self._securities: dict[str, SecurityInfoV392] = {}
        if securities is not None:
            self.add_many(securities)

    # ---------------- 添加证券 ----------------
    def add(self, security: SecurityInfoV392) -> None:
        """添加单只股票。"""
        if not isinstance(security, SecurityInfoV392):
            raise UniverseErrorV392("security must be SecurityInfoV392.")
        security.normalize()
        if not security.code:
            raise UniverseErrorV392("Security code is empty.")
        self._securities[security.code] = security

    def add_many(self, securities: _IterableV392[SecurityInfoV392]) -> None:
        """批量添加股票。"""
        for security in securities:
            self.add(security)

    # ---------------- 从 DataFrame 加载 ----------------
    def load_dataframe(
        self,
        df: pd.DataFrame,
        code_column: str = "code",
        name_column: str = "name",
        list_date_column: str = "list_date",
        delist_date_column: str = "delist_date",
        st_column: str = "is_st",
        star_st_column: str = "is_star_st",
        suspended_column: str = "is_suspended",
        exchange_column: str = "exchange",
        security_type_column: str = "security_type",
        industry_column: str = "industry",
    ) -> None:
        """从 DataFrame 加载历史股票元数据。最低要求：code 列。"""
        if df is None or df.empty:
            raise UniverseErrorV392("Security dataframe is empty.")
        if code_column not in df.columns:
            raise UniverseErrorV392(f"Missing code column: {code_column}")
        for _, row in df.iterrows():
            code = normalize_stock_code_v392(row[code_column])
            security = SecurityInfoV392(
                code=code,
                name=(
                    str(row[name_column])
                    if name_column in df.columns and pd.notna(row[name_column])
                    else ""
                ),
                exchange=(
                    str(row[exchange_column])
                    if exchange_column in df.columns and pd.notna(row[exchange_column])
                    else ""
                ),
                list_date=(
                    self._safe_date(row[list_date_column])
                    if list_date_column in df.columns
                    else None
                ),
                delist_date=(
                    self._safe_date(row[delist_date_column])
                    if delist_date_column in df.columns
                    else None
                ),
                is_st=(
                    self._safe_bool(row[st_column])
                    if st_column in df.columns
                    else False
                ),
                is_star_st=(
                    self._safe_bool(row[star_st_column])
                    if star_st_column in df.columns
                    else False
                ),
                is_suspended=(
                    self._safe_bool(row[suspended_column])
                    if suspended_column in df.columns
                    else False
                ),
                security_type=(
                    str(row[security_type_column])
                    if security_type_column in df.columns
                    and pd.notna(row[security_type_column])
                    else "stock"
                ),
                industry=(
                    str(row[industry_column])
                    if industry_column in df.columns and pd.notna(row[industry_column])
                    else None
                ),
            )
            self.add(security)

    def load_csv(self, path: str | _PathV392, **kwargs) -> None:
        """从 CSV 加载股票元数据。"""
        path = _PathV392(path)
        if not path.exists():
            raise UniverseErrorV392(f"Universe file does not exist: {path}")
        df = pd.read_csv(path)
        self.load_dataframe(df, **kwargs)

    # ---------------- 查询 ----------------
    def get(self, code) -> _OptionalV392[SecurityInfoV392]:
        """获取单只股票。"""
        normalized = normalize_stock_code_v392(code)
        return self._securities.get(normalized)

    def codes(self) -> list[str]:
        """获取全部股票代码。"""
        return list(self._securities.keys())

    def __len__(self) -> int:
        return len(self._securities)

    # ---------------- 历史有效性 ----------------
    def was_listed(self, code, date) -> bool:
        """判断股票在指定日期是否已经上市。"""
        security = self.get(code)
        if security is None:
            return False
        if security.list_date is None:
            # 没有上市日期时不能安全判断，默认 False（防 PIT 泄漏）
            return False
        ts = normalize_date_v392(date)
        if self.config.include_listing_day:
            return ts >= security.list_date
        return ts > security.list_date

    def was_delisted(self, code, date) -> bool:
        """判断股票在指定日期是否已经退市。"""
        security = self.get(code)
        if security is None:
            return False
        if security.delist_date is None:
            return False
        ts = normalize_date_v392(date)
        return ts >= security.delist_date

    def is_active(self, code, date) -> bool:
        """判断股票在指定日期是否处于有效上市状态（已上市 + 未退市）。"""
        security = self.get(code)
        if security is None:
            return False
        ts = normalize_date_v392(date)
        # 上市日期未知：为避免 survivorship / look-ahead，默认不视为已上市
        if security.list_date is None:
            return False
        if self.config.include_listing_day:
            if ts < security.list_date:
                return False
        else:
            if ts <= security.list_date:
                return False
        if (
            self.config.exclude_delisted
            and security.delist_date is not None
        ):
            if ts >= security.delist_date:
                return False
        return True

    # ---------------- ST / 停牌 ----------------
    def is_st(self, code, date=None) -> bool:
        """判断 ST（简化字段；严格 PIT 需按日期状态表）。"""
        security = self.get(code)
        if security is None:
            return False
        return bool(security.is_st)

    def is_star_st(self, code, date=None) -> bool:
        """判断 *ST。"""
        security = self.get(code)
        if security is None:
            return False
        return bool(security.is_star_st)

    def is_suspended(self, code, date=None) -> bool:
        """判断停牌。"""
        security = self.get(code)
        if security is None:
            return False
        return bool(security.is_suspended)

    # ---------------- 指定日期历史股票池 ----------------
    def get_universe(
        self, date, codes: _OptionalV392[_SequenceV392] = None
    ) -> list[str]:
        """获取指定日期的历史股票池（已上市/未退市/非ST/非*ST/非停牌/普通股）。"""
        ts = normalize_date_v392(date)
        candidates = (
            normalize_codes_v392(codes)
            if codes is not None
            else self.codes()
        )
        result = []
        for code in candidates:
            security = self.get(code)
            if security is None:
                continue
            # 上市 / 退市
            if not self.is_active(code, ts):
                continue
            # ST
            if self.config.exclude_st and self.is_st(code, ts):
                continue
            if self.config.exclude_star_st and self.is_star_st(code, ts):
                continue
            # 停牌
            if self.config.exclude_suspended and self.is_suspended(code, ts):
                continue
            # 股票类型
            if (
                self.config.only_common_stock
                and security.security_type not in {"stock", "A", "common_stock", ""}
            ):
                continue
            result.append(code)
        return sorted(result)

    def get_universe_by_dates(
        self,
        dates: _IterableV392,
        codes: _OptionalV392[_SequenceV392] = None,
    ) -> dict[str, list[str]]:
        """获取多个日期的历史股票池。"""
        result = {}
        for date in dates:
            ts = normalize_date_v392(date)
            key = ts.strftime("%Y-%m-%d")
            result[key] = self.get_universe(ts, codes=codes)
        return result

    def universe_dataframe(
        self,
        dates: _IterableV392,
        codes: _OptionalV392[_SequenceV392] = None,
    ) -> pd.DataFrame:
        """将历史股票池转成 DataFrame（date, code）。"""
        rows = []
        universe_by_date = self.get_universe_by_dates(dates, codes=codes)
        for date_str, codes_list in universe_by_date.items():
            for code in codes_list:
                rows.append({"date": pd.Timestamp(date_str), "code": code})
        if not rows:
            return pd.DataFrame(columns=["date", "code"])
        return (
            pd.DataFrame(rows)
            .sort_values(["date", "code"])
            .reset_index(drop=True)
        )

    # ---------------- 统计 ----------------
    def count(
        self, date, codes: _OptionalV392[_SequenceV392] = None
    ) -> int:
        """指定日期股票数量。"""
        return len(self.get_universe(date, codes=codes))

    def summary(self, date) -> dict:
        """指定日期股票池统计。"""
        ts = normalize_date_v392(date)
        all_codes = self.codes()
        listed = active = st = star_st = suspended = 0
        for code in all_codes:
            if self.was_listed(code, ts):
                listed += 1
            if self.is_active(code, ts):
                active += 1
            if self.is_st(code, ts):
                st += 1
            if self.is_star_st(code, ts):
                star_st += 1
            if self.is_suspended(code, ts):
                suspended += 1
        return {
            "date": ts.strftime("%Y-%m-%d"),
            "total_metadata": len(all_codes),
            "listed": listed,
            "active": active,
            "st": st,
            "star_st": star_st,
            "suspended": suspended,
            "final_universe": self.count(ts),
        }

    # ---------------- 内部工具 ----------------
    @staticmethod
    def _safe_date(value):
        """安全日期转换。"""
        if value is None:
            return None
        if pd.isna(value):
            return None
        try:
            return normalize_date_v392(value)
        except Exception:
            return None

    @staticmethod
    def _safe_bool(value) -> bool:
        """安全布尔转换。"""
        if value is None:
            return False
        if pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        value = str(value).strip().lower()
        return value in {"1", "true", "yes", "y", "是", "st", "*st"}


# ----------------------------------------------------------------------------
# 模块级便捷函数
# ----------------------------------------------------------------------------
def create_universe_from_csv_v392(
    path: str | _PathV392,
    config: _OptionalV392[UniverseConfigV392] = None,
) -> HistoricalUniverseV392:
    """从 CSV 创建 HistoricalUniverseV392。"""
    universe = HistoricalUniverseV392(config=config)
    universe.load_csv(path)
    return universe


def create_universe_from_codes_v392(
    codes: _SequenceV392,
    config: _OptionalV392[UniverseConfigV392] = None,
) -> HistoricalUniverseV392:
    """根据股票代码创建简单 Universe（list_date=1900-01-01，用于单元测试/原型）。"""
    universe = HistoricalUniverseV392(config=config)
    for code in normalize_codes_v392(codes):
        security = SecurityInfoV392(
            code=code,
            list_date=pd.Timestamp("1900-01-01"),
            security_type="stock",
        )
        universe.add(security)
    return universe
