"""V3.5 TimeSeriesSplit：时间序列切分（Train / Validation / Test）。

关键原则：不能随机打乱时间序列，否则极易造成未来信息泄漏。
"""

from __future__ import annotations

import pandas as pd


class TimeSeriesSplit:
    def split(
        self,
        data: pd.DataFrame,
        train_ratio: float = 0.60,
        validation_ratio: float = 0.20,
    ):
        n = len(data)
        train_end = int(n * train_ratio)
        validation_end = train_end + int(n * validation_ratio)
        train = data.iloc[:train_end]
        validation = data.iloc[train_end:validation_end]
        test = data.iloc[validation_end:]
        return {
            "train": train,
            "validation": validation,
            "test": test,
        }
