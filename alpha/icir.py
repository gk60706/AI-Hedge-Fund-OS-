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


# ============================================================================
# V3.9.1 unified research engine - ICIR helpers
# ============================================================================


def icir(ic_values) -> float:
    values = np.asarray(list(ic_values), dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return 0.0
    std = values.std(ddof=1)
    if std == 0:
        return 0.0
    return float(values.mean() / std)


def positive_ic_ratio(ic_values) -> float:
    values = np.asarray(list(ic_values), dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return 0.0
    return float((values > 0).mean())
