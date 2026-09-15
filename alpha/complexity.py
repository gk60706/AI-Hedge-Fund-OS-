from __future__ import annotations


class ComplexityPenalty:
    def __init__(self, penalty_per_node=0.01):
        self.penalty_per_node = penalty_per_node

    def calculate(self, expression):
        complexity = expression.complexity()
        return complexity * self.penalty_per_node

    def adjusted_score(self, expression, raw_score):
        return raw_score - self.calculate(expression)
