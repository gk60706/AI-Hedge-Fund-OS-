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
