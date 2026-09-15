from __future__ import annotations

import random

from alpha.expression import AlphaExpression
from alpha.generator import (
    FEATURES,
    BINARY_OPERATORS,
    UNARY_OPERATORS,
)


class AlphaMutation:
    def mutate(self, expression, probability=0.20):
        if random.random() > probability:
            return expression
        return self._mutate_node(expression)

    def _mutate_node(self, node):
        if random.random() < 0.25:
            return AlphaExpression(
                operator="FEATURE",
                feature=random.choice(FEATURES),
            )
        if node.children and random.random() < 0.6:
            index = random.randrange(len(node.children))
            node.children[index] = self._mutate_node(
                node.children[index]
            )
            return node
        if node.operator in (BINARY_OPERATORS):
            node.operator = random.choice(BINARY_OPERATORS)
        elif node.operator in (UNARY_OPERATORS):
            node.operator = random.choice(UNARY_OPERATORS)
        return node
