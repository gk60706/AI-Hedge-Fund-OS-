from __future__ import annotations

import pandas as pd


class QuantileAnalyzer:
    def analyze(
        self,
        factor: pd.Series,
        forward_return: pd.Series,
        quantiles: int = 5,
    ):
        data = pd.concat(
            [
                factor.rename("factor"),
                forward_return.rename("forward_return"),
            ],
            axis=1,
        ).dropna()
        if data.empty:
            return {}
        data["quantile"] = pd.qcut(
            data["factor"],
            q=quantiles,
            labels=False,
            duplicates="drop",
        )
        result = (
            data.groupby("quantile")["forward_return"].mean()
        )
        return result.to_dict()

    def long_short_spread(
        self,
        factor,
        forward_return,
        quantiles=5,
    ):
        data = pd.concat(
            [
                factor.rename("factor"),
                forward_return.rename("forward_return"),
            ],
            axis=1,
        ).dropna()
        if data.empty:
            return 0.0
        data["q"] = pd.qcut(
            data["factor"],
            q=quantiles,
            labels=False,
            duplicates="drop",
        )
        groups = (
            data.groupby("q")["forward_return"].mean()
        )
        if len(groups) < 2:
            return 0.0
        return float(
            groups.iloc[-1] - groups.iloc[0]
        )
