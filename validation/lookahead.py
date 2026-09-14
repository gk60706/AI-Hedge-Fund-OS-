from __future__ import annotations

import pandas as pd


class LookaheadDetector:
    def detect(
        self,
        df: pd.DataFrame,
        date_column: str = "date",
        available_column: str = "available_date",
    ) -> dict:
        if (
            date_column not in df.columns
            or available_column not in df.columns
        ):
            return {
                "valid": False,
                "error": ("缺少 date 或 " "available_date"),
            }
        work = df.copy()
        work[date_column] = pd.to_datetime(work[date_column])
        work[available_column] = pd.to_datetime(work[available_column])
        violations = (
            work[work[available_column] > work[date_column]]
        )
        return {
            "valid": violations.empty,
            "violations": len(violations),
        }
