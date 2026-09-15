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
