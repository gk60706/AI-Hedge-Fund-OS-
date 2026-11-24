from __future__ import annotations

import pandas as pd

from alpha.ic import (
    InformationCoefficient,
)
from alpha.icir import (
    ICIRCalculator,
)
from alpha.quantile import (
    QuantileAnalyzer,
)
from alpha.correlation import (
    FactorCorrelation,
)
from alpha.scorer import (
    AlphaScorer,
)


class FactorExperiment:
    def __init__(
        self,
    ):
        self.ic = (InformationCoefficient())
        self.icir = (ICIRCalculator())
        self.quantile = (QuantileAnalyzer())
        self.scorer = (AlphaScorer())

    def run(
        self,
        factor: pd.Series,
        forward_return: pd.Series,
        ic_history: list[float],
    ):
        current_ic = (
            self.ic.rank_ic(
                factor,
                forward_return,
            )
        )
        ic_values = (
            ic_history + [current_ic]
        )
        icir = (
            self.icir.calculate(
                ic_values
            )
        )
        quantiles = (
            self.quantile.analyze(
                factor,
                forward_return,
            )
        )
        long_short = (
            self.quantile.long_short_spread(
                factor,
                forward_return,
            )
        )
        mean_ic = (
            sum(ic_values) / len(ic_values)
        )
        positive_ratio = (
            sum(value > 0 for value in ic_values) / len(ic_values)
        )
        score = self.scorer.score(
            mean_ic=mean_ic,
            icir=icir,
            long_short=long_short,
            stability=positive_ratio,
        )
        return {
            "ic": current_ic,
            "mean_ic": mean_ic,
            "icir": icir,
            "quantiles": quantiles,
            "long_short": long_short,
            "stability": positive_ratio,
            "score": score,
            "classification": self.scorer.classify(score),
        }
