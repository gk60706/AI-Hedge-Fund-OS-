from __future__ import annotations

from typing import Any

import akshare as ak
import pandas as pd


class MarketDataError(RuntimeError):
    pass


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_a_share_quote(code: str) -> dict[str, Any]:
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        raise ValueError("股票代码必须是 6 位数字，例如 300394")
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as exc:
        raise MarketDataError(f"AkShare 获取 A 股实时行情失败: {exc}") from exc
    if df is None or df.empty:
        raise MarketDataError("AkShare 返回空行情数据。")
    row = df.loc[df["代码"].astype(str).str.zfill(6) == code]
    if row.empty:
        raise MarketDataError(f"没有找到股票 {code}，请确认代码。")
    item = row.iloc[0]

    def value(column: str) -> Any:
        if column in df.columns:
            return item[column]
        return None

    return {
        "code": code,
        "name": value("名称"),
        "latest_price": _to_float(value("最新价")),
        "change_pct": _to_float(value("涨跌幅")),
        "change_amount": _to_float(value("涨跌额")),
        "volume_lots": _to_float(value("成交量")),
        "amount_yuan": _to_float(value("成交额")),
        "amplitude_pct": _to_float(value("振幅")),
        "high": _to_float(value("最高")),
        "low": _to_float(value("最低")),
        "open": _to_float(value("今开")),
        "prev_close": _to_float(value("昨收")),
        "turnover_pct": _to_float(value("换手率")),
        "pe_dynamic": _to_float(value("市盈率-动态")),
        "pb": _to_float(value("市净率")),
        "market_cap": _to_float(value("总市值")),
        "source": "AkShare stock_zh_a_spot_em",
    }
