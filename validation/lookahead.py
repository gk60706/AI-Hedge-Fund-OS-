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



# ============================================================================
# V3.9.1 unified research engine - look-ahead detection
# ============================================================================


def find_lookahead(panel: pd.DataFrame) -> list:
    """返回 available_date 晚于 date 的违规行索引（未来数据泄漏）。"""
    violations: list = []
    if panel is None or panel.empty:
        return violations
    if "available_date" not in panel.columns or "date" not in panel.columns:
        return violations
    for idx, row in panel.iterrows():
        if pd.isna(row["available_date"]):
            continue
        if pd.Timestamp(row["available_date"]) > pd.Timestamp(row["date"]):
            violations.append(idx)
    return violations
