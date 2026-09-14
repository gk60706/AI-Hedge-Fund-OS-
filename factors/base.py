from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Factor(ABC):
    name: str = "base"

    @abstractmethod
    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        """
        返回与 data.index 对齐的因子值。
        """
        raise NotImplementedError
