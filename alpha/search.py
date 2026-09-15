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
# ============================================================================
# V3.9.1 unified research engine - alpha search (dump semantics)
# ============================================================================


class AlphaSearch:
    def __init__(self, seed: int = 42, max_depth: int = 3, correlation_threshold: float = 0.90):
        self.generator = AlphaGeneratorV391(seed=seed, max_depth=max_depth)
        self.evaluator = ExpressionEvaluator()
        self.deduplicator = AlphaDeduplicatorV391(correlation_threshold)

    def search(self, train: pd.DataFrame, n_candidates: int = 300, horizon: int = 1) -> list[dict]:
        work = train.copy().sort_values(["date", "code"]).reset_index(drop=True)
        future_return = work.groupby("code")["close"].shift(-horizon) / work["close"] - 1
        results: list[dict] = []
        for _ in range(n_candidates):
            expression = self.generator.generate()
            try:
                signal = self.evaluator.evaluate(expression, work)
            except Exception:
                continue
            if signal.notna().sum() < 50:
                continue
            if not self.deduplicator.accept(expression, signal):
                continue
            ic_series = cross_sectional_ic(signal, future_return, work["date"])
            current_ic = mean_ic(ic_series)
            current_icir = icir(ic_series)
            qspread = quantile_spread(signal, future_return, work["date"])
            results.append(
                {
                    "expression": expression,
                    "signal": signal,
                    "ic_series": ic_series,
                    "ic": current_ic,
                    "icir": current_icir,
                    "positive_ic_ratio": positive_ic_ratio(ic_series),
                    "q5_q1": qspread,
                    "complexity": expression.complexity(),
                    "complexity_penalty": complexity_penalty_v391(expression.complexity()),
                }
            )
        return sorted(
            results,
            key=lambda x: (abs(x["ic"]) if x["ic"] == x["ic"] else -1),
            reverse=True,
        )


import pandas as pd  # noqa: E402
from alpha.complexity import complexity_penalty_v391  # noqa: E402
from alpha.deduplicator import AlphaDeduplicatorV391  # noqa: E402
from alpha.evaluator import ExpressionEvaluator  # noqa: E402
from alpha.generator import AlphaGeneratorV391  # noqa: E402
from alpha.ic import cross_sectional_ic, mean_ic  # noqa: E402
from alpha.icir import icir, positive_ic_ratio  # noqa: E402
from alpha.quantile import quantile_spread  # noqa: E402
