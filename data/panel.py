"""
AI Hedge Fund OS
V3.9.2
data/panel.py

作用：
1. 构建统一的多股票、多日期 Panel 数据结构
2. 对接 data/schema.py
3. 提供 PIT 数据过滤
4. 提供 forward return 计算
5. 提供横截面切片
6. 提供交易状态过滤
7. 提供基础数据质量检查

核心数据结构：date × code
一行 = 一个股票在一个交易日的数据
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
import numpy as np
import pandas as pd
from .schema import (
    REQUIRED_COLUMNS,
    SchemaConfig,
    SchemaError,
    normalize_schema,
)


# ============================================================
# 1. Panel 配置
# ============================================================
@dataclass(frozen=True)
class PanelConfig:
    """Panel 数据配置。"""

    # schema strict 校验
    schema_strict: bool = True
    # 是否删除重复 date + code
    drop_duplicates: bool = True
    # forward return 使用的价格字段
    price_column: str = "close"
    # 默认前瞻收益周期
    default_forward_horizon: int = 1


# ============================================================
# 2. PanelData
# ============================================================
class PanelData:
    """
    V3.9.2 标准 Panel 数据容器。

    内部核心 DataFrame：date / code / open / high / low / close /
    volume / amount / turnover / ...
    """

    def __init__(
        self,
        data: pd.DataFrame,
        config: Optional[PanelConfig] = None,
    ):
        self.config = config or PanelConfig()
        self._data = normalize_schema(
            data,
            SchemaConfig(strict=self.config.schema_strict),
        )
        self._prepare()

    # ========================================================
    # 3. 数据准备
    # ========================================================
    def _prepare(self) -> None:
        """内部数据准备。"""
        df = self._data.copy()
        # 日期排序
        df = df.sort_values(["date", "code"], kind="mergesort")
        # 删除重复 date + code
        if self.config.drop_duplicates:
            df = df.drop_duplicates(subset=["date", "code"], keep="last")
        # 重建 index
        df = df.reset_index(drop=True)
        self._data = df

    # ========================================================
    # 4. DataFrame 接口
    # ========================================================
    @property
    def data(self) -> pd.DataFrame:
        """返回底层 DataFrame（copy，防止外部破坏内部数据）。"""
        return self._data.copy()

    def copy(self) -> "PanelData":
        """复制 Panel。"""
        return PanelData(self._data.copy(), self.config)

    # ========================================================
    # 5. 基础信息
    # ========================================================
    @property
    def dates(self) -> pd.DatetimeIndex:
        """所有交易日期。"""
        return pd.DatetimeIndex(
            self._data["date"].dropna().drop_duplicates().sort_values()
        )

    @property
    def codes(self) -> list:
        """所有股票代码。"""
        return sorted(
            self._data["code"].dropna().astype(str).unique().tolist()
        )

    @property
    def n_rows(self) -> int:
        """数据行数。"""
        return len(self._data)

    @property
    def n_dates(self) -> int:
        """交易日数量。"""
        return self._data["date"].nunique()

    @property
    def n_codes(self) -> int:
        """股票数量。"""
        return self._data["code"].nunique()

    @property
    def start_date(self) -> Optional[pd.Timestamp]:
        """起始日期。"""
        if self._data.empty:
            return None
        return self._data["date"].min()

    @property
    def end_date(self) -> Optional[pd.Timestamp]:
        """结束日期。"""
        if self._data.empty:
            return None
        return self._data["date"].max()

    # ========================================================
    # 6. repr
    # ========================================================
    def __repr__(self) -> str:
        return (
            f"PanelData(rows={self.n_rows}, "
            f"dates={self.n_dates}, codes={self.n_codes}, "
            f"start={self.start_date}, end={self.end_date})"
        )

    # ========================================================
    # 7. 日期过滤
    # ========================================================
    def between(self, start_date=None, end_date=None) -> "PanelData":
        """按日期范围过滤。"""
        df = self._data.copy()
        if start_date is not None:
            start_date = pd.Timestamp(start_date)
            df = df[df["date"] >= start_date]
        if end_date is not None:
            end_date = pd.Timestamp(end_date)
            df = df[df["date"] <= end_date]
        return PanelData(df, self.config)

    # ========================================================
    # 8. 指定股票过滤
    # ========================================================
    def select_codes(self, codes: Sequence[str]) -> "PanelData":
        """选择指定股票。"""
        normalized_codes = {str(code).zfill(6) for code in codes}
        mask = self._data["code"].astype(str).isin(normalized_codes)
        return PanelData(self._data.loc[mask].copy(), self.config)

    # ========================================================
    # 9. 单只股票
    # ========================================================
    def select_code(self, code: str) -> "PanelData":
        """选择单只股票。"""
        code = str(code).zfill(6)
        return self.select_codes([code])

    # ========================================================
    # 10. 单日横截面
    # ========================================================
    def cross_section(self, date, tradeable_only: bool = False) -> pd.DataFrame:
        """获取某一天的横截面（Alpha Engine 最重要的数据接口之一）。"""
        date = pd.Timestamp(date).normalize()
        df = self._data[self._data["date"] == date].copy()
        if tradeable_only:
            df = df[df["is_tradeable"]]
        return df.reset_index(drop=True)

    # ========================================================
    # 11. 多日横截面
    # ========================================================
    def cross_sections(
        self, dates: Optional[Iterable] = None, tradeable_only: bool = False
    ):
        """按日期生成横截面，返回 date -> DataFrame。"""
        if dates is None:
            dates = self.dates
        result = {}
        for date in dates:
            result[date] = self.cross_section(date, tradeable_only=tradeable_only)
        return result

    # ========================================================
    # 12. PIT 过滤
    # ========================================================
    def pit_filter(self, as_of_date=None, strict: bool = True) -> "PanelData":
        """
        Point-in-Time 数据过滤。
        核心规则：available_date <= as_of_date（或 <= date 行级）。
        """
        df = self._data.copy()
        if "available_date" not in df.columns:
            return self
        if as_of_date is not None:
            as_of_date = pd.Timestamp(as_of_date).normalize()
            mask = df["available_date"].isna() | (
                df["available_date"] <= as_of_date
            )
        else:
            # 行级：available_date <= date
            mask = df["available_date"].isna() | (
                df["available_date"] <= df["date"]
            )
        df = df.loc[mask].copy()
        return PanelData(df, self.config)

    # ========================================================
    # 13. PIT 审计
    # ========================================================
    def pit_violations(self) -> pd.DataFrame:
        """返回所有潜在 PIT 穿越数据（available_date > date）。"""
        df = self._data.copy()
        if "available_date" not in df.columns:
            return pd.DataFrame(columns=df.columns)
        mask = (
            df["available_date"].notna() & (df["available_date"] > df["date"])
        )
        return df.loc[mask].copy()

    # ========================================================
    # 14. 只保留可交易股票
    # ========================================================
    def tradeable(self) -> "PanelData":
        """只保留可交易股票。"""
        if "is_tradeable" not in self._data:
            return self.copy()
        df = self._data[self._data["is_tradeable"]].copy()
        return PanelData(df, self.config)

    # ========================================================
    # 15. 删除停牌
    # ========================================================
    def remove_suspended(self) -> "PanelData":
        """删除停牌数据。"""
        if "suspended" not in self._data:
            return self.copy()
        df = self._data[~self._data["suspended"]].copy()
        return PanelData(df, self.config)

    # ========================================================
    # 16. 删除涨停
    # ========================================================
    def remove_limit_up(self) -> "PanelData":
        """删除涨停股票（次日买入模拟）。"""
        if "limit_up" not in self._data:
            return self.copy()
        df = self._data[~self._data["limit_up"]].copy()
        return PanelData(df, self.config)

    # ========================================================
    # 17. 删除跌停
    # ========================================================
    def remove_limit_down(self) -> "PanelData":
        """删除跌停股票（卖出能力模拟）。"""
        if "limit_down" not in self._data:
            return self.copy()
        df = self._data[~self._data["limit_down"]].copy()
        return PanelData(df, self.config)

    # ========================================================
    # 18. 添加历史收益率
    # ========================================================
    def add_returns(
        self,
        price_column: str = "close",
        periods: int = 1,
        column_name: Optional[str] = None,
    ) -> "PanelData":
        """计算历史收益率 P(t)/P(t-n)-1。"""
        if price_column not in self._data.columns:
            raise SchemaError(f"不存在价格字段：{price_column}")
        if periods <= 0:
            raise ValueError("periods 必须大于 0")
        df = self._data.copy()
        df = df.sort_values(["code", "date"])
        if column_name is None:
            column_name = f"return_{periods}d"
        df[column_name] = (
            df.groupby("code")[price_column].pct_change(periods=periods)
        )
        df = df.sort_values(["date", "code"])
        return PanelData(df, self.config)

    # ========================================================
    # 19. 添加 Forward Return
    # ========================================================
    def add_forward_return(
        self,
        horizon: int = 1,
        price_column: str = "close",
        column_name: Optional[str] = None,
    ) -> "PanelData":
        """
        计算未来收益：close(t+h)/close(t)-1。
        这是 Alpha Research 的核心标签。
        实际交易应由 Backtest Engine 用下一交易日开盘处理。
        """
        if price_column not in self._data.columns:
            raise SchemaError(f"不存在价格字段：{price_column}")
        if horizon <= 0:
            raise ValueError("horizon 必须大于 0")
        df = self._data.copy()
        df = df.sort_values(["code", "date"])
        if column_name is None:
            column_name = f"forward_return_{horizon}d"
        future_price = df.groupby("code")[price_column].shift(-horizon)
        current_price = df[price_column]
        df[column_name] = future_price / current_price - 1.0
        df = df.sort_values(["date", "code"])
        return PanelData(df, self.config)

    # ========================================================
    # 20. Open-to-Close Forward Return
    # ========================================================
    def add_next_open_return(
        self, column_name: str = "next_open_return"
    ) -> "PanelData":
        """
        计算 close(t+1)/open(t+1)-1（t 收盘信号 → t+1 开盘执行 → t+1 日内收益）。
        """
        df = self._data.copy()
        df = df.sort_values(["code", "date"])
        next_open = df.groupby("code")["open"].shift(-1)
        next_close = df.groupby("code")["close"].shift(-1)
        df[column_name] = next_close / next_open - 1.0
        df = df.sort_values(["date", "code"])
        return PanelData(df, self.config)

    # ========================================================
    # 21. 未来最高收益
    # ========================================================
    def add_forward_max_return(
        self, horizon: int = 5, column_name: Optional[str] = None
    ) -> "PanelData":
        """未来 N 个交易日内的最高收益（研究指标，非可交易收益）。"""
        if horizon <= 0:
            raise ValueError("horizon 必须大于 0")
        df = self._data.copy()
        df = df.sort_values(["code", "date"])
        if column_name is None:
            column_name = f"forward_max_return_{horizon}d"
        result = np.full(len(df), np.nan, dtype=float)
        for code, group in df.groupby("code", sort=False):
            index = group.index
            highs = group["high"].to_numpy()
            closes = group["close"].to_numpy()
            values = np.full(len(group), np.nan)
            for i in range(len(group)):
                end = min(i + horizon, len(group) - 1)
                if i >= end:
                    continue
                future_high = np.max(highs[i + 1 : end + 1])
                if np.isfinite(closes[i]) and closes[i] > 0:
                    values[i] = future_high / closes[i] - 1.0
            result[df.index.get_indexer(index)] = values
        df[column_name] = result
        df = df.sort_values(["date", "code"])
        return PanelData(df, self.config)

    # ========================================================
    # 22. 未来最大回撤
    # ========================================================
    def add_forward_max_drawdown(
        self, horizon: int = 5, column_name: Optional[str] = None
    ) -> "PanelData":
        """未来 N 个交易日最大回撤（Alpha 风险评估）。"""
        if horizon <= 0:
            raise ValueError("horizon 必须大于 0")
        df = self._data.copy()
        df = df.sort_values(["code", "date"])
        if column_name is None:
            column_name = f"forward_max_drawdown_{horizon}d"
        result = np.full(len(df), np.nan, dtype=float)
        for code, group in df.groupby("code", sort=False):
            index = group.index
            lows = group["low"].to_numpy()
            closes = group["close"].to_numpy()
            values = np.full(len(group), np.nan)
            for i in range(len(group)):
                end = min(i + horizon, len(group) - 1)
                if i >= end:
                    continue
                current_close = closes[i]
                if not np.isfinite(current_close) or current_close <= 0:
                    continue
                future_lows = lows[i + 1 : end + 1]
                future_lows = future_lows[np.isfinite(future_lows)]
                if len(future_lows) == 0:
                    continue
                lowest = np.min(future_lows)
                values[i] = lowest / current_close - 1.0
            result[df.index.get_indexer(index)] = values
        df[column_name] = result
        df = df.sort_values(["date", "code"])
        return PanelData(df, self.config)

    # ========================================================
    # 23. 交易日序号
    # ========================================================
    def add_trading_day_index(
        self, column_name: str = "trading_day_index"
    ) -> "PanelData":
        """添加全市场交易日序号。"""
        df = self._data.copy()
        dates = pd.Series(sorted(df["date"].dropna().unique()))
        mapping = {date: idx for idx, date in enumerate(dates)}
        df[column_name] = df["date"].map(mapping).astype("Int64")
        return PanelData(df, self.config)

    # ========================================================
    # 24. 每日股票数量
    # ========================================================
    def daily_stock_count(self) -> pd.DataFrame:
        """统计每日股票数量（数据完整性 / Survivorship Bias 检查）。"""
        return (
            self._data.groupby("date")["code"]
            .nunique()
            .rename("stock_count")
            .reset_index()
        )

    # ========================================================
    # 25. 每日可交易股票数量
    # ========================================================
    def daily_tradeable_count(self) -> pd.DataFrame:
        """每日可交易股票数量。"""
        df = self._data.copy()
        return (
            df.groupby("date")["is_tradeable"].sum()
            .rename("tradeable_count")
            .reset_index()
        )

    # ========================================================
    # 26. 股票覆盖率
    # ========================================================
    def coverage_by_code(self) -> pd.DataFrame:
        """统计每只股票的数据覆盖情况。"""
        return (
            self._data.groupby("code")
            .agg(
                start_date=("date", "min"),
                end_date=("date", "max"),
                observations=("date", "count"),
            )
            .reset_index()
        )

    # ========================================================
    # 27. 数据质量报告
    # ========================================================
    def quality_report(self) -> dict:
        """生成 Panel 数据质量报告。"""
        df = self._data
        duplicate_count = int(
            df.duplicated(subset=["date", "code"]).sum()
        )
        missing_close = int(df["close"].isna().sum())
        missing_open = int(df["open"].isna().sum())
        pit_violation_count = len(self.pit_violations())
        return {
            "rows": len(df),
            "dates": df["date"].nunique(),
            "stocks": df["code"].nunique(),
            "start_date": (df["date"].min() if not df.empty else None),
            "end_date": (df["date"].max() if not df.empty else None),
            "duplicate_rows": duplicate_count,
            "missing_open": missing_open,
            "missing_close": missing_close,
            "pit_violations": pit_violation_count,
        }

    # ========================================================
    # 28. 获取指定字段
    # ========================================================
    def columns(self, columns: Sequence[str]) -> pd.DataFrame:
        """获取指定字段。"""
        missing = [c for c in columns if c not in self._data.columns]
        if missing:
            raise SchemaError("不存在字段：" + ", ".join(missing))
        return self._data[list(columns)].copy()

    # ========================================================
    # 29. 添加字段
    # ========================================================
    def assign(self, **kwargs) -> "PanelData":
        """类似 pandas.DataFrame.assign。"""
        df = self._data.copy()
        for key, value in kwargs.items():
            if callable(value):
                df[key] = value(df)
            else:
                df[key] = value
        return PanelData(df, self.config)

    # ========================================================
    # 30. 过滤
    # ========================================================
    def filter(self, mask) -> "PanelData":
        """根据布尔条件过滤。"""
        df = self._data.loc[mask].copy()
        return PanelData(df, self.config)

    # ========================================================
    # 31. MultiIndex Panel
    # ========================================================
    def to_multiindex(self) -> pd.DataFrame:
        """转换成 date × code MultiIndex（因子矩阵 / Alpha 矩阵 / ML 输入）。"""
        return self._data.set_index(["date", "code"]).sort_index()

    # ========================================================
    # 32. 普通 DataFrame
    # ========================================================
    def to_dataframe(self) -> pd.DataFrame:
        """返回普通 DataFrame。"""
        return self._data.copy()

    # ========================================================
    # 33. 保存 CSV
    # ========================================================
    def to_csv(self, path: str, index: bool = False) -> None:
        """保存 Panel。"""
        self._data.to_csv(path, index=index, encoding="utf-8-sig")

    # ========================================================
    # 34. 从 CSV 创建
    # ========================================================
    @classmethod
    def from_csv(
        cls,
        path: str,
        config: Optional[PanelConfig] = None,
        **read_csv_kwargs,
    ) -> "PanelData":
        """从 CSV 加载 Panel。"""
        df = pd.read_csv(path, **read_csv_kwargs)
        return cls(df, config=config)

    # ========================================================
    # 35. 从 DataFrame 创建
    # ========================================================
    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, config: Optional[PanelConfig] = None
    ) -> "PanelData":
        """从 DataFrame 创建 Panel。"""
        return cls(df, config=config)


# ============================================================
# 36. 便利函数：计算 Forward Return
# ============================================================
def add_forward_return(
    df: pd.DataFrame,
    horizon: int = 1,
    price_column: str = "close",
) -> pd.DataFrame:
    """DataFrame 便利函数，不需要显式创建 PanelData。"""
    panel = PanelData(df)
    return panel.add_forward_return(horizon=horizon, price_column=price_column).data


# ============================================================
# 37. 便利函数：横截面
# ============================================================
def get_cross_section(
    df: pd.DataFrame,
    date,
    tradeable_only: bool = False,
) -> pd.DataFrame:
    """获取某个日期横截面。"""
    panel = PanelData(df)
    return panel.cross_section(date, tradeable_only=tradeable_only)
