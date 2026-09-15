from __future__ import annotations

import numpy as np
import pandas as pd


class AlphaOperators:
    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def sub(a, b):
        return a - b

    @staticmethod
    def mul(a, b):
        return a * b

    @staticmethod
    def div(a, b):
        denominator = b.replace(0, np.nan)
        return a / denominator

    @staticmethod
    def neg(a):
        return -a

    @staticmethod
    def abs(a):
        return a.abs()

    @staticmethod
    def log(a):
        return np.log(a.abs() + 1e-8)

    @staticmethod
    def rank(a):
        return a.rank(pct=True)

    @staticmethod
    def zscore(a):
        std = a.std()
        if std == 0 or np.isnan(std):
            return a * 0
        return (a - a.mean()) / std
