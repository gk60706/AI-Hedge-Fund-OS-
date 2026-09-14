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
