"""真实 A 股历史行情接口 (V3.3)

基于 AkShare 获取 A 股日线历史行情，统一字段命名并做数值化处理。
"""
from __future__ import annotations

import akshare as ak
import pandas as pd


class HistoricalDataError(RuntimeError):
    """历史行情获取失败。"""

    pass


def normalize_code(code: str) -> str:
    """规范化股票代码：剥离 sh/sz/bj 前缀，校验为 6 位数字。

    :param code: 如 "300394"、"sh600519"、"SZ000001"。
    :return: 6 位数字代码。
    """
    code = code.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        code = code.removeprefix(prefix)
    if not code.isdigit() or len(code) != 6:
        raise ValueError("股票代码必须是6位数字，例如300394")
    return code


def get_daily_history(
    code: str,
    start_date: str = "20240101",
    end_date: str = "20261231",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取单只 A 股日线历史行情（前复权）。

    :param code: 股票代码（支持 sh/sz/bj 前缀）。
    :param start_date: 起始日期，格式 YYYYMMDD。
    :param end_date: 结束日期，格式 YYYYMMDD。
    :param adjust: 复权方式，默认 qfq（前复权）。
    :return: 标准化 DataFrame（date 为 datetime，行情列为数值）。
    """
    code = normalize_code(code)
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except Exception as exc:
        raise HistoricalDataError(f"获取{code}历史行情失败:{exc}") from exc

    if df is None or df.empty:
        raise HistoricalDataError(f"{code}没有返回历史行情")

    rename_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "change_pct",
        "涨跌额": "change",
        "换手率": "turnover",
    }
    df = df.rename(columns=rename_map)
    df["date"] = pd.to_datetime(df["date"])

    numeric_columns = [
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "change_pct",
        "turnover",
    ]
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.sort_values("date")
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    return df
