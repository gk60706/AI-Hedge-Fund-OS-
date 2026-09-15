"""V3.9.1 alpha mutation on expression trees."""
from __future__ import annotations

import numpy as np


def mutate(expression, rng, probability: float = 0.15):
    """以 probability 概率对表达式做一次变异（否则原样返回）。"""
    if rng.random() >= probability:
        return expression
    return _mutate_node(expression, rng)


def _mutate_node(node, rng):
    from alpha.expression import AlphaExpression
    from alpha.generator import FEATURES_V391

    if not node.children:
        return AlphaExpression(
            feature=str(rng.choice(FEATURES_V391))
        )
    if len(node.children) == 2:
        pick = int(rng.integers(0, 3))
        if pick == 0:
            return AlphaExpression(
                operator=node.operator,
                children=[
                    mutate(node.children[0], rng, 1.0),
                    node.children[1],
                ],
            )
        if pick == 1:
            return AlphaExpression(
                operator=node.operator,
                children=[
                    node.children[0],
                    mutate(node.children[1], rng, 1.0),
                ],
            )
        return AlphaExpression(
            operator=str(
                rng.choice(["add", "sub", "mul", "div"])
            ),
            children=list(node.children),
        )
    if rng.random() < 0.5:
        return AlphaExpression(
            operator=node.operator,
            children=[mutate(node.children[0], rng, 1.0)],
        )
    return AlphaExpression(
        operator=str(
            rng.choice(["neg", "abs", "log", "rank", "zscore"])
        ),
        children=list(node.children),
    )
