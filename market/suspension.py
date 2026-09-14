"""V3.6 SuspensionDetector：停牌检测。

收盘价缺失 / 成交量缺失或为 0 → 视为停牌，不能交易。
"""

from __future__ import annotations

import pandas as pd


class SuspensionDetector:
    @staticmethod
    def is_suspended(row: pd.Series) -> bool:
        if row is None:
            return True
        close = row.get("收盘")
        volume = row.get("成交量")
        if pd.isna(close):
            return True
        if pd.isna(volume):
            return True
        if float(volume) <= 0:
            return True
        return False
