from __future__ import annotations

import pandas as pd


class InformationCoefficient:
    @staticmethod
    def rank_ic(
        factor: pd.Series,
        forward_return: pd.Series,
    ) -> float:
        data = pd.concat(
            [
                factor.rename("factor"),
                forward_return.rename("forward_return"),
            ],
            axis=1,
        ).dropna()
        if len(data) < 10:
            return 0.0
        return float(
            data["factor"].corr(
                data["forward_return"],
                method="spearman",
            )
        )


# ============================================================================
# V3.9.1 unified research engine - cross-sectional IC helpers
# ============================================================================


def cross_sectional_ic(
    signal,
    forward_return,
    dates,
    min_observations: int = 5,
):
    """按 date 分组计算每日横截面秩 IC；样本不足返回 NaN。"""
    frame = pd.DataFrame(
        {
            "date": dates,
            "signal": signal,
            "fwd": forward_return,
        }
    )
    frame = frame.dropna(subset=["signal", "fwd"])

    def _daily_ic(group):
        if len(group) < min_observations:
            return float("nan")
        return float(
            group["signal"].rank().corr(group["fwd"].rank())
        )

    return frame.groupby("date").apply(_daily_ic, include_groups=False)


def mean_ic(ic_values) -> float:
    values = pd.Series(ic_values).dropna()
    if values.empty:
        return 0.0
    return float(values.mean())

from alpha.icir import icir, positive_ic_ratio  # noqa: E402,F401
