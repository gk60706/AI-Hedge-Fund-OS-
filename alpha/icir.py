from __future__ import annotations

import numpy as np


class ICIRCalculator:
    def calculate(
        self,
        ic_series,
    ):
        values = np.asarray(ic_series, dtype=float,)
        values = values[np.isfinite(values)]
        if len(values) < 2:
            return 0.0
        std = values.std(ddof=1)
        if std == 0:
            return 0.0
        return float(values.mean() / std)
