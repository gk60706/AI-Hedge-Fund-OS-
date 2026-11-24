"""V3.9.1 alpha crossover between expression trees."""
from __future__ import annotations


def crossover(expression_a, expression_b, rng):
    """简单占位交叉：随机取一个父代（完整表达式层面）。"""
    return expression_a if rng.random() < 0.5 else expression_b
