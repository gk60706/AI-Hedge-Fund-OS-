from __future__ import annotations

import random

from alpha.generator import AlphaGenerator
from alpha.evaluator import AlphaEvaluator
from alpha.complexity import ComplexityPenalty
from alpha.deduplicator import AlphaDeduplicator


class AlphaSearchEngine:
    def __init__(self):
        self.generator = AlphaGenerator()
        self.evaluator = AlphaEvaluator()
        self.penalty = ComplexityPenalty()
        self.deduplicator = AlphaDeduplicator()

    def generate_candidates(self, size=100, depth=3):
        candidates = self.generator.generate_population(size, depth)
        return self.deduplicator.deduplicate(candidates)

    def evaluate_candidates(
        self,
        candidates,
        features,
        forward_return,
    ):
        results = []
        for expression in candidates:
            try:
                signal = self.evaluator.evaluate(expression, features)
                data = signal.to_frame("factor")
                data["return"] = forward_return
                data = data.dropna()
                if len(data) < 30:
                    continue
                ic = data["factor"].corr(
                    data["return"],
                    method="spearman",
                )
                score = abs(ic)
                adjusted = self.penalty.adjusted_score(
                    expression,
                    score,
                )
                results.append(
                    {
                        "expression": expression,
                        "formula": expression.to_string(),
                        "ic": float(ic),
                        "raw_score": float(score),
                        "complexity": expression.complexity(),
                        "adjusted_score": float(adjusted),
                    }
                )
            except Exception:
                continue
        results.sort(
            key=lambda x: x["adjusted_score"],
            reverse=True,
        )
        return results
