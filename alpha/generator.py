from __future__ import annotations

import random

from alpha.expression import AlphaExpression

FEATURES = [
    "pe_inverse",
    "pb_inverse",
    "ps_inverse",
    "momentum_20",
    "momentum_60",
    "momentum_120",
    "roe",
    "roic",
    "revenue_growth",
    "profit_growth",
    "volatility_20",
    "turnover",
    "amount_20",
]

BINARY_OPERATORS = ["ADD", "SUB", "MUL", "DIV"]
UNARY_OPERATORS = ["NEG", "ABS", "LOG", "RANK", "ZSCORE"]


class AlphaGenerator:
    def random_leaf(self):
        if random.random() < 0.9:
            return AlphaExpression(
                operator="FEATURE",
                feature=random.choice(FEATURES),
            )
        return AlphaExpression(
            operator="CONST",
            value=random.uniform(-1, 1),
        )

    def generate(self, depth=2):
        if depth <= 0:
            return self.random_leaf()
        probability = random.random()
        if probability < 0.45:
            operator = random.choice(BINARY_OPERATORS)
            return AlphaExpression(
                operator=operator,
                children=[
                    self.generate(depth - 1),
                    self.generate(depth - 1),
                ],
            )
        operator = random.choice(UNARY_OPERATORS)
        return AlphaExpression(
            operator=operator,
            children=[self.generate(depth - 1)],
        )

    def generate_population(self, size=100, max_depth=3):
        return [
            self.generate(random.randint(1, max_depth))
            for _ in range(size)
        ]


# ============================================================================
# V3.9.1 unified research engine - generator for panel-compatible features
# ============================================================================

FEATURES_V391 = [
    "value",
    "momentum",
    "quality",
    "volatility",
    "liquidity",
    "turnover",
    "pe",
    "pb",
]


class AlphaGeneratorV391:
    def __init__(self, seed: int = 42, max_depth: int = 3):
        self.random = random.Random(seed)
        self.max_depth = max_depth

    def _leaf(self):
        return AlphaExpressionV391.feature_node(
            self.random.choice(FEATURES_V391)
        )

    def generate(self, depth: int = 1) -> AlphaExpressionV391:
        if depth >= self.max_depth or self.random.random() < 0.4:
            return self._leaf()
        operator = self.random.choice(BINARY_OPERATORS)
        left = self.generate(depth + 1)
        right = self.generate(depth + 1)
        return AlphaExpressionV391(
            operator=operator,
            children=[left, right],
        )
from alpha.expression import AlphaExpressionV391
