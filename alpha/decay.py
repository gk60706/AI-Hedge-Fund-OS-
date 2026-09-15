from __future__ import annotations

import pandas as pd

from alpha.ic import (
    InformationCoefficient,
)


class FactorDecayAnalyzer:
    def analyze(
        self,
        factor: pd.Series,
        close: pd.Series,
        horizons=None,
    ):
        if horizons is None:
            horizons = [1, 3, 5, 10, 20,]
        result = {}
        ic = (InformationCoefficient())
        for horizon in horizons:
            forward_return = (
                close.shift(-horizon) / close - 1
            )
            result[horizon] = ic.rank_ic(
                factor,
                forward_return,
            )
        return result


# ============================================================================
# V3.9.1 unified research engine - decay profile
# ============================================================================


def decay_profile(
    signal,
    close,
    horizons=(1, 3, 5, 10, 20),
) -> dict:
    ic = InformationCoefficient()
    result = {}
    for horizon in horizons:
        fwd = close.shift(-horizon) / close - 1
        result[int(horizon)] = ic.rank_ic(signal, fwd)
    return result
