from __future__ import annotations

import pandas as pd


class CleanBacktestDataset:
    def __init__(
        self,
        as_of_date,
    ):
        self.as_of_date = (
            pd.Timestamp(as_of_date)
        )

    def filter_available(
        self,
        df: pd.DataFrame,
        available_column="available_date",
    ):
        work = df.copy()
        work[available_column] = pd.to_datetime(work[available_column])
        return (
            work[work[available_column] <= self.as_of_date].copy()
        )

    def remove_duplicates(
        self,
        df: pd.DataFrame,
        subset=None,
    ):
        return df.drop_duplicates(subset=subset)

    def clean(
        self,
        df: pd.DataFrame,
        available_column="available_date",
        subset=None,
    ):
        result = self.filter_available(df, available_column,)
        result = self.remove_duplicates(result, subset,)
        return result.reset_index(drop=True)
