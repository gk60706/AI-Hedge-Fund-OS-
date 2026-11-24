"""V1.2 Alpha 因子发现 Agent：从候选因子池中自动发现 Alpha 因子并生成公式。"""

import random

_CANDIDATE_FACTORS = [
    "momentum",
    "volume_breakout",
    "ma_cross",
    "capital_flow",
    "volatility",
]

_FORMULAS = {
    "momentum": "close/close_20-1",
    "volume_breakout": "volume/MA(volume,20)",
    "ma_cross": "MA5-MA20",
    "capital_flow": "buy_money-sell_money",
    "volatility": "std(return)",
}


class AlphaAgent:
    """Alpha 因子发现 Agent。

    从候选因子池中随机选择因子并生成对应公式表达式，
    供策略生成 Agent 使用。
    """

    def __init__(self, factors: list | None = None) -> None:
        self.factors = list(factors) if factors else list(_CANDIDATE_FACTORS)

    def discover(self, market_data=None) -> dict:
        """发现一个 Alpha 因子。

        :param market_data: 市场数据（当前版本为占位，保留接口）
        :return: ``{"factor": str, "formula": str}``
        """
        factor = random.choice(self.factors)
        return {"factor": factor, "formula": self.generate_formula(factor)}

    def generate_formula(self, factor: str) -> str:
        """返回指定因子的公式表达式。未知因子抛出 KeyError。"""
        return _FORMULAS[factor]
