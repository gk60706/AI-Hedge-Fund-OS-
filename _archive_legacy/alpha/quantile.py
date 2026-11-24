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


# ============================================================================
# V3.9.1 unified research engine - quantile spread
# ============================================================================


def quantile_spread(
    signal,
    forward_return,
    dates,
    quantiles: int = 5,
) -> float:
    frame = pd.DataFrame(
        {
            "date": dates,
            "signal": signal,
            "fwd": forward_return,
        }
    ).dropna(subset=["signal", "fwd"])

    def _spread(group):
        if len(group) < quantiles:
            return float("nan")
        try:
            group = group.copy()
            group["q"] = pd.qcut(group["signal"], quantiles, labels=False)
        except ValueError:
            return float("nan")
        means = group.groupby("q")["fwd"].mean()
        if len(means) < 2:
            return float("nan")
        return float(means.iloc[-1] - means.iloc[0])

    spreads = frame.groupby("date").apply(_spread, include_groups=False).dropna()
    if spreads.empty:
        return 0.0
    return float(spreads.mean())
