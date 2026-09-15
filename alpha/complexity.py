from __future__ import annotations


class ComplexityPenalty:
    def __init__(self, penalty_per_node=0.01):
        self.penalty_per_node = penalty_per_node

    def calculate(self, expression):
        complexity = expression.complexity()
        return complexity * self.penalty_per_node

    def adjusted_score(self, expression, raw_score):
        return raw_score - self.calculate(expression)


# ============================================================================
# V3.9.1 unified research engine - complexity penalty function
# ============================================================================


def complexity_penalty(expression, penalty_per_node: float = 0.5) -> float:
    return float(expression.complexity()) * penalty_per_node


# ============================================================================
# V3.9.1 unified research engine - complexity penalty (v391, int arg, dump)
# ============================================================================


def complexity_penalty_v391(complexity: int, weight: float = 0.5) -> float:
    return float(complexity * weight)
