"""AkShare 行情数据提供者（只读）。

安全边界：本模块只做「行情获取」，不含任何交易接口。
"""
from __future__ import annotations

from datetime import date
from typing import Any

import akshare as ak
import pandas as pd

from app.market.schemas import HistoryBar

# AkShare 日线接口返回的中文列名 -> 统一英文列名
_HIST_COLUMNS = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "涨跌幅": "pct_change",
}


class MarketDataProvider:
    """基于 AkShare 的 A 股行情数据提供者。"""

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """将任意格式的股票代码规范化为 6 位数字，如 '1' -> '000001'。"""
        digits = "".join(ch for ch in symbol.strip() if ch.isdigit())
        if not digits or len(digits) > 6:
            raise ValueError(f"非法的股票代码: {symbol!r}")
        return digits.zfill(6)

    def get_daily_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取个股日线历史行情（默认前复权），返回统一英文列名的 DataFrame。"""
        symbol = self.normalize_symbol(symbol)
        end = (end_date or date.today().isoformat()).replace("-", "")
        start = start_date.replace("-", "") if start_date else f"{int(end[:4]) - 1}{end[4:]}"

        raw = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start,
            end_date=end,
            adjust=adjust,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()

        df = raw.rename(columns=_HIST_COLUMNS).copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        for col in ("open", "close", "high", "low", "amount", "pct_change"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        return df.reset_index(drop=True)

    def to_history_response(self, symbol: str, df: pd.DataFrame, adjust: str = "qfq") -> list[HistoryBar]:
        """将清洗后的 DataFrame 转换为 HistoryBar 列表。"""
        bars: list[HistoryBar] = []
        for _, row in df.iterrows():
            bars.append(
                HistoryBar(
                    date=row["date"],
                    open=float(row["open"]),
                    close=float(row["close"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    volume=int(row["volume"]),
                    amount=float(row.get("amount", 0.0) or 0.0),
                    pct_change=float(row["pct_change"]) if pd.notna(row.get("pct_change")) else None,
                )
            )
        return bars

    def get_spot_quote(self, symbol: str) -> dict[str, Any]:
        """获取全市场实时快照中的单只股票行情。"""
        symbol = self.normalize_symbol(symbol)
        spot = ak.stock_zh_a_spot_em()
        if spot is None or spot.empty:
            raise KeyError("未获取到市场快照数据")
        row = spot.loc[spot["代码"].astype(str) == symbol]
        if row.empty:
            raise KeyError(f"未找到股票 {symbol}")
        return row.iloc[0].to_dict()

    def get_individual_info(self, symbol: str) -> dict[str, Any]:
        """获取个股基本信息（总市值、行业、上市时间等）。"""
        symbol = self.normalize_symbol(symbol)
        info = ak.stock_individual_info_em(symbol=symbol)
        if info is None or info.empty:
            return {}
        return dict(zip(info["item"], info["value"]))
