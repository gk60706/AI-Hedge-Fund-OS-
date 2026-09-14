from __future__ import annotations

import numpy as np
import pandas as pd


class Orthogonalizer:
    def orthogonalize(
        self,
        target: pd.Series,
        controls: pd.DataFrame,
    ) -> pd.Series:
        data = pd.concat(
            [
                target.rename("target"),
                controls,
            ],
            axis=1,
        ).dropna()
        if data.empty:
            return target * np.nan
        x = data[controls.columns].to_numpy(dtype=float)
        y = data["target"].to_numpy(dtype=float)
        x = np.column_stack(
            [
                np.ones(len(x)),
                x,
            ]
        )
        beta = np.linalg.lstsq(
            x,
            y,
            rcond=None,
        )[0]
        fitted = x @ beta
        residual = y - fitted
        result = pd.Series(
            residual,
            index=data.index,
            name=target.name,
        )
        return result.reindex(target.index)
