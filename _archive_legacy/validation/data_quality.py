"""V3.6 DataQualityChecker：真实历史数据质量检查。

真实历史数据最怕“垃圾数据进入模型”。检查项：
- 空数据
- 日期未排序
- 重复日期
- 无效价格（开盘/收盘/最高/最低 <= 0）
- 最高价 < 最低价（高低倒挂）
"""

from __future__ import annotations

import pandas as pd


class DataQualityChecker:
    def check(self, df: pd.DataFrame) -> dict:
        issues = []

        if df.empty:
            issues.append("EMPTY_DATA")
            return {"valid": False, "issues": issues}

        if not df["日期"].is_monotonic_increasing:
            issues.append("DATE_NOT_SORTED")

        if df["日期"].duplicated().any():
            issues.append("DUPLICATE_DATES")

        for column in ["开盘", "收盘", "最高", "最低"]:
            if (df[column] <= 0).any():
                issues.append(f"INVALID_{column}")

        if (df["最高"] < df["最低"]).any():
            issues.append("HIGH_LOW_ERROR")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "rows": len(df),
            "start": str(df["日期"].min()),
            "end": str(df["日期"].max()),
        }
# ============================================================================
# V3.9.1 unified research engine - data quality audit (dump)
# ============================================================================


def audit_panel(df: pd.DataFrame) -> list[str]:
    errors = []
    if df.empty:
        errors.append("Panel为空")
        return errors
    if df.duplicated(["date", "code"]).any():
        errors.append("存在重复 date/code")
    for column in ["open", "high", "low", "close"]:
        if column not in df.columns:
            continue
        values = pd.to_numeric(df[column], errors="coerce")
        if (values <= 0).any():
            errors.append(f"{column}存在非正价格")
    if {"high", "low"}.issubset(df.columns):
        bad = df["high"] < df["low"]
        if bad.any():
            errors.append("存在 high < low")
    return errors


import pandas as pd  # noqa: E402
