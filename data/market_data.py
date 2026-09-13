"""V3.0.1 Real Market Data Engine：AkShare 真实行情封装。

API Key 只从 .env 读取；行情数据来自 AkShare 公开接口。
"""
from __future__ import annotations

from typing import Any

import akshare as ak
import pandas as pd

from data.cache import DataCache
from data.schemas import StockQuote


class MarketDataError(RuntimeError):
    pass


class MarketData:
    def __init__(self):
        self.cache = DataCache(
            ttl_seconds=60,
        )

    @staticmethod
    def normalize_code(code: str) -> str:
        code = (
            str(code)
            .strip()
            .lower()
        )
        for prefix in (
            "sh",
            "sz",
            "bj",
        ):
            code = code.removeprefix(prefix)
        if (
            not code.isdigit()
            or len(code) != 6
        ):
            raise ValueError("股票代码必须是6位数字")
        return code

    @staticmethod
    def _float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def get_spot(self, code: str) -> StockQuote:
        code = self.normalize_code(code)
        cache_key = f"quote_{code}"
        cached = self.cache.get(cache_key)
        if cached:
            return StockQuote(**cached)
        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as exc:
            raise MarketDataError(
                f"获取A股实时行情失败: {exc}"
            ) from exc
        if df is None or df.empty:
            raise MarketDataError("行情接口返回空数据")
        df["代码"] = (
            df["代码"]
            .astype(str)
            .str.zfill(6)
        )
        row = df[df["代码"] == code]
        if row.empty:
            raise MarketDataError(
                f"没有找到股票: {code}"
            )
        item = row.iloc[0]

        def value(column: str):
            if column in df.columns:
                return item[column]
            return None

        quote = StockQuote(
            code=code,
            name=str(value("名称") or ""),
            latest_price=self._float(value("最新价")),
            change_pct=self._float(value("涨跌幅")),
            change_amount=self._float(value("涨跌额")),
            volume=self._float(value("成交量")),
            amount=self._float(value("成交额")),
            amplitude=self._float(value("振幅")),
            high=self._float(value("最高")),
            low=self._float(value("最低")),
            open=self._float(value("今开")),
            prev_close=self._float(value("昨收")),
            turnover=self._float(value("换手率")),
            pe=self._float(value("市盈率-动态")),
            pb=self._float(value("市净率")),
            market_cap=self._float(value("总市值")),
        )
        self.cache.set(cache_key, quote.to_dict())
        return quote

    def get_daily(
        self,
        code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        code = self.normalize_code(code)
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception as exc:
            raise MarketDataError(
                f"获取历史行情失败: {exc}"
            ) from exc
        if df is None or df.empty:
            raise MarketDataError(
                f"{code} 没有历史行情数据"
            )
        return df

    def get_all_spot(self) -> pd.DataFrame:
        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as exc:
            raise MarketDataError(
                f"获取全市场行情失败: {exc}"
            ) from exc
        if df is None or df.empty:
            raise MarketDataError("全市场行情为空")
        df["代码"] = (
            df["代码"]
            .astype(str)
            .str.zfill(6)
        )
        return df
