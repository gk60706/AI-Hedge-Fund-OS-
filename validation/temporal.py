from __future__ import annotations

import pandas as pd


class TemporalValidator:
    def validate(
        self,
        df: pd.DataFrame,
        feature_date: str,
        label_date: str,
    ) -> dict:
        work = df.copy()
        work[feature_date] = pd.to_datetime(work[feature_date])
        work[label_date] = pd.to_datetime(work[label_date])
        violations = work[work[feature_date] >= work[label_date]]
        return {
            "valid": violations.empty,
            "violations": len(violations),
        }



# ============================================================================
# V3.9.1 unified research engine - temporal validation
# ============================================================================


def validate_temporal(panel: pd.DataFrame) -> list[str]:
    """时间顺序校验：date 必须单调、无重复（code 内）。"""
    errors: list[str] = []
    if panel is None or panel.empty:
        return errors
    if "date" not in panel.columns:
        errors.append("panel 缺少 date 列")
        return errors
    if "code" not in panel.columns:
        errors.append("panel 缺少 code 列")
        return errors
    for code, group in panel.groupby("code", sort=False):
        dates = pd.to_datetime(group["date"])
        if not dates.is_monotonic_increasing:
            errors.append(f"{code}: date 非单调")
        if dates.duplicated().any():
            errors.append(f"{code}: date 存在重复")
    return errors
