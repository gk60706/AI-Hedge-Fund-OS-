from __future__ import annotations

import pandas as pd


class LeakageDetector:
    def check_feature_target(
        self,
        df: pd.DataFrame,
        feature_columns: list[str],
        target_column: str,
        date_column: str = "date",
    ) -> dict:
        issues = []
        if date_column not in df.columns:
            issues.append("MISSING_DATE")
            return {
                "valid": False,
                "issues": issues,
            }
        dates = pd.to_datetime(df[date_column])
        if not dates.is_monotonic_increasing:
            issues.append("DATE_NOT_SORTED")
        if target_column not in df.columns:
            issues.append("MISSING_TARGET")
        for column in feature_columns:
            if column not in df.columns:
                issues.append(f"MISSING_FEATURE:{column}")
        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }
