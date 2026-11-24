"""V3.0.2 5000 A 股自动扫描：股票池清洗（ST/退/停牌过滤）。"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd


class AShareUniverse:
    def __init__(self):
        self.exclude_keywords = [
            "ST",
            "*ST",
            "退",
        ]

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        if "名称" in data.columns:
            pattern = "|".join(
                re.escape(k)
                for k in self.exclude_keywords
            )
            mask = (
                ~data["名称"]
                .astype(str)
                .str.contains(
                    pattern,
                    case=False,
                    na=False,
                )
            )
            data = data[mask]
        if "最新价" in data.columns:
            data = data[
                data["最新价"].fillna(0) > 0
            ]
        return data.reset_index(drop=True)
