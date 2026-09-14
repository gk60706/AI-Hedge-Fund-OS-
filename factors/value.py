"""价值因子 (V0.5)

PE 估值评分：低估值获得更高分数。
"""


def pe_factor(pe: float) -> float:
    """PE 估值评分。

    :param pe: 市盈率
    :return: 0-100 的估值得分（越低 PE 得分越高）
    """
    if pe < 20:
        return 90
    elif pe < 40:
        return 70
    elif pe < 80:
        return 50
    else:
        return 20



# ============================================================================
# V3.8 AI Alpha Research Engine - value factor classes
# ============================================================================
import numpy as np
import pandas as pd

from factors.base import Factor


class PEFactor(Factor):
    name = "pe_inverse"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        pe = pd.to_numeric(data["pe"], errors="coerce",)
        # PE <= 0 通常代表亏损/异常
        pe = pe.where(pe > 0)
        return 1.0 / pe


class PBFactor(Factor):
    name = "pb_inverse"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        pb = pd.to_numeric(data["pb"], errors="coerce",)
        pb = pb.where(pb > 0)
        return 1.0 / pb


class PSFactor(Factor):
    name = "ps_inverse"

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        ps = pd.to_numeric(data["ps"], errors="coerce",)
        ps = ps.where(ps > 0)
        return 1.0 / ps
