"""V3.6 PriceLoader：标准化历史数据（统一字段、排序、去重、数值化）。"""

from __future__ import annotations

import pandas as pd

from data.akshare_client import AkShareClientV36


class PriceLoader:
    def __init__(self):
        self.client = AkShareClientV36()

    def load(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self.client.get_daily(
            code=code,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        required = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"{code}缺少字段: {missing}")

        df = df.copy()
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期")
        df = df.drop_duplicates("日期")
        numeric_columns = ["开盘", "收盘", "最高", "最低", "成交量", "成交额"]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        return df


# ============================================================================
# V3.9.1 unified research engine - normalization
# ============================================================================

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def normalize_daily(df: pd.DataFrame, code: str) -> pd.DataFrame:
    frame = df.copy()
    frame.columns = [str(c).strip() for c in frame.columns]
    mapping = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    frame = frame.rename(columns=mapping)
    for col in ["open", "high", "low", "close"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["code"] = code
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame.dropna(subset=["date", "close"]).reset_index(drop=True)
