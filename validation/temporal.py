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
