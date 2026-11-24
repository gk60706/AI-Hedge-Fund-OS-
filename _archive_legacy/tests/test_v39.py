# -*- coding: utf-8 -*-
"""Tests for V3.9 AI Alpha Discovery Engine."""
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ---- alpha: expression tree ----
from alpha.expression import AlphaExpression
from alpha.operators import AlphaOperators
from alpha.generator import (
    FEATURES,
    BINARY_OPERATORS,
    UNARY_OPERATORS,
    AlphaGenerator,
)
from alpha.evaluator import AlphaEvaluator
from alpha.complexity import ComplexityPenalty
from alpha.deduplicator import AlphaDeduplicator
from alpha.search import AlphaSearchEngine
from alpha.library import AlphaLibrary

# ---- evolution: genetic alpha ----
from evolution.alpha_genome import AlphaGenome
from evolution.alpha_mutation import AlphaMutation
from evolution.alpha_crossover import AlphaCrossover
from evolution.alpha_evolution import AlphaEvolution

# ---- validation: OOS ----
from validation.alpha_oos import AlphaOOSValidator

# ---- main ----
import main_v39


# =====================================================================
# alpha/expression.py
# =====================================================================
class TestAlphaExpression:
    def test_leaf_complexity(self):
        expr = AlphaExpression(operator="FEATURE", feature="roe")
        assert expr.complexity() == 1

    def test_binary_complexity(self):
        expr = AlphaExpression(
            operator="ADD",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(operator="FEATURE", feature="pe_inverse"),
            ],
        )
        assert expr.complexity() == 3

    def test_to_string_feature(self):
        expr = AlphaExpression(operator="FEATURE", feature="momentum_20")
        assert expr.to_string() == "momentum_20"

    def test_to_string_const(self):
        expr = AlphaExpression(operator="CONST", value=0.43212)
        assert expr.to_string() == "0.4321"

    def test_to_string_unary(self):
        expr = AlphaExpression(
            operator="RANK",
            children=[AlphaExpression(operator="FEATURE", feature="roe")],
        )
        assert expr.to_string() == "RANK(roe)"

    def test_to_string_binary(self):
        expr = AlphaExpression(
            operator="SUB",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(operator="FEATURE", feature="volatility_20"),
            ],
        )
        assert expr.to_string() == "(roe SUB volatility_20)"

    def test_to_string_deep(self):
        expr = AlphaExpression(
            operator="MUL",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(
                    operator="LOG",
                    children=[
                        AlphaExpression(operator="FEATURE", feature="pe_inverse")
                    ],
                ),
            ],
        )
        assert expr.to_string() == "(roe MUL LOG(pe_inverse))"


# =====================================================================
# alpha/operators.py
# =====================================================================
class TestAlphaOperators:
    def test_add_sub_mul(self):
        a = pd.Series([1.0, 2.0, 3.0])
        b = pd.Series([10.0, 20.0, 30.0])
        assert list(AlphaOperators.add(a, b)) == [11.0, 22.0, 33.0]
        assert list(AlphaOperators.sub(a, b)) == [-9.0, -18.0, -27.0]
        assert list(AlphaOperators.mul(a, b)) == [10.0, 40.0, 90.0]

    def test_div_replaces_zero_with_nan(self):
        a = pd.Series([1.0, 2.0, 3.0])
        b = pd.Series([2.0, 0.0, 4.0])
        out = AlphaOperators.div(a, b)
        assert out.iloc[0] == pytest.approx(0.5)
        assert np.isnan(out.iloc[1])
        assert out.iloc[2] == pytest.approx(0.75)

    def test_neg_abs_log(self):
        a = pd.Series([-2.0, 2.0])
        assert list(AlphaOperators.neg(a)) == [2.0, -2.0]
        assert list(AlphaOperators.abs(a)) == [2.0, 2.0]
        assert list(AlphaOperators.log(a)) == pytest.approx(
            [np.log(2.0 + 1e-8), np.log(2.0 + 1e-8)]
        )

    def test_rank_pct(self):
        a = pd.Series([3.0, 1.0, 2.0])
        out = AlphaOperators.rank(a)
        assert list(out) == pytest.approx([1.0, 1.0 / 3, 2.0 / 3])

    def test_zscore(self):
        a = pd.Series([1.0, 2.0, 3.0])
        out = AlphaOperators.zscore(a)
        assert out.mean() == pytest.approx(0.0, abs=1e-12)
        assert out.std() == pytest.approx(1.0, abs=1e-12)

    def test_zscore_constant(self):
        a = pd.Series([2.0, 2.0, 2.0])
        out = AlphaOperators.zscore(a)
        assert list(out) == [0.0, 0.0, 0.0]


# =====================================================================
# alpha/generator.py
# =====================================================================
class TestAlphaGenerator:
    def test_features_list(self):
        assert len(FEATURES) == 13
        assert "pe_inverse" in FEATURES
        assert "amount_20" in FEATURES

    def test_operators_lists(self):
        assert BINARY_OPERATORS == ["ADD", "SUB", "MUL", "DIV"]
        assert UNARY_OPERATORS == ["NEG", "ABS", "LOG", "RANK", "ZSCORE"]

    def test_random_leaf_is_leaf(self):
        generator = AlphaGenerator()
        leaf = generator.random_leaf()
        assert leaf.children == []
        assert leaf.operator in ("FEATURE", "CONST")
        if leaf.operator == "FEATURE":
            assert leaf.feature in FEATURES

    def test_generate_zero_depth_is_leaf(self):
        generator = AlphaGenerator()
        expr = generator.generate(depth=0)
        assert expr.children == []

    def test_generate_population_size(self):
        generator = AlphaGenerator()
        population = generator.generate_population(size=50, max_depth=2)
        assert len(population) == 50
        assert all(isinstance(e, AlphaExpression) for e in population)


# =====================================================================
# alpha/evaluator.py
# =====================================================================
class TestAlphaEvaluator:
    def _features(self, n=100):
        return pd.DataFrame(
            {
                "roe": np.linspace(-1, 1, n),
                "momentum_20": np.linspace(1, 2, n),
                "volatility_20": np.linspace(2, 1, n),
                "pe_inverse": np.linspace(0.01, 0.05, n),
            }
        )

    def test_evaluate_feature(self):
        features = self._features()
        out = AlphaEvaluator().evaluate(
            AlphaExpression(operator="FEATURE", feature="roe"),
            features,
        )
        assert list(out) == pytest.approx(list(features["roe"]))

    def test_evaluate_missing_feature_raises(self):
        features = self._features()
        with pytest.raises(ValueError):
            AlphaEvaluator().evaluate(
                AlphaExpression(operator="FEATURE", feature="missing"),
                features,
            )

    def test_evaluate_const(self):
        features = self._features()
        out = AlphaEvaluator().evaluate(
            AlphaExpression(operator="CONST", value=0.5),
            features,
        )
        assert len(out) == len(features)
        assert list(out.unique()) == [0.5]

    def test_evaluate_expression_tree(self):
        features = self._features()
        expr = AlphaExpression(
            operator="SUB",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(operator="FEATURE", feature="volatility_20"),
            ],
        )
        out = AlphaEvaluator().evaluate(expr, features)
        expected = features["roe"] - features["volatility_20"]
        assert list(out) == pytest.approx(list(expected))

    def test_evaluate_unknown_operator_raises(self):
        features = self._features()
        with pytest.raises(ValueError):
            AlphaEvaluator().evaluate(
                AlphaExpression(operator="UNKNOWN", children=[]),
                features,
            )


# =====================================================================
# alpha/complexity.py
# =====================================================================
class TestComplexityPenalty:
    def test_calculate(self):
        penalty = ComplexityPenalty(penalty_per_node=0.01)
        expr = AlphaExpression(
            operator="ADD",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(operator="FEATURE", feature="pe_inverse"),
            ],
        )
        assert penalty.calculate(expr) == pytest.approx(0.03)

    def test_adjusted_score(self):
        penalty = ComplexityPenalty(penalty_per_node=0.01)
        expr = AlphaExpression(operator="FEATURE", feature="roe")
        assert penalty.adjusted_score(expr, 0.10) == pytest.approx(0.09)


# =====================================================================
# alpha/deduplicator.py
# =====================================================================
class TestAlphaDeduplicator:
    def test_signature_deterministic(self):
        dedup = AlphaDeduplicator()
        expr = AlphaExpression(
            operator="ADD",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(operator="FEATURE", feature="momentum_20"),
            ],
        )
        assert dedup.signature(expr) == dedup.signature(expr)
        assert len(dedup.signature(expr)) == 64  # sha256 hex

    def test_deduplicate_keeps_order(self):
        dedup = AlphaDeduplicator()
        a = AlphaExpression(operator="FEATURE", feature="roe")
        b = AlphaExpression(operator="FEATURE", feature="momentum_20")
        c = AlphaExpression(operator="FEATURE", feature="roe")
        out = dedup.deduplicate([a, b, c])
        assert len(out) == 2
        assert out[0] is a
        assert out[1] is b


# =====================================================================
# alpha/search.py
# =====================================================================
class TestAlphaSearchEngine:
    def test_generate_candidates_deduplicated(self):
        engine = AlphaSearchEngine()
        candidates = engine.generate_candidates(size=200, depth=2)
        assert len(candidates) <= 200
        # no duplicate signatures
        signatures = [engine.deduplicator.signature(c) for c in candidates]
        assert len(signatures) == len(set(signatures))

    def test_evaluate_candidates_returns_sorted(self):
        rng = np.random.default_rng(1)
        n = 500
        features = pd.DataFrame(
            {
                "roe": rng.normal(0, 1, n),
                "momentum_20": rng.normal(0, 1, n),
            }
        )
        hidden = features["roe"] * 0.5 + features["momentum_20"] * 0.3
        returns = pd.Series(hidden * 0.01 + rng.normal(0, 0.02, n))
        engine = AlphaSearchEngine()
        # force population to include the hidden-style expression
        candidates = [
            AlphaExpression(
                operator="ADD",
                children=[
                    AlphaExpression(operator="FEATURE", feature="roe"),
                    AlphaExpression(operator="FEATURE", feature="momentum_20"),
                ],
            ),
            AlphaExpression(operator="FEATURE", feature="roe"),
            AlphaExpression(operator="CONST", value=0.123),
        ]
        results = engine.evaluate_candidates(candidates, features, returns)
        assert len(results) == 3
        scores = [r["adjusted_score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        assert results[0]["formula"] == "(roe ADD momentum_20)"
        assert results[0]["ic"] > 0

    def test_evaluate_short_data_skipped(self):
        features = pd.DataFrame({"roe": [1.0, 2.0]})
        returns = pd.Series([0.01, 0.02])
        engine = AlphaSearchEngine()
        candidates = [AlphaExpression(operator="FEATURE", feature="roe")]
        results = engine.evaluate_candidates(candidates, features, returns)
        assert results == []


# =====================================================================
# alpha/library.py
# =====================================================================
class TestAlphaLibrary:
    def test_save_load_top(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "alpha_library.json")
            lib = AlphaLibrary(path)
            assert lib.load() == []
            lib.save({"formula": "roe", "adjusted_score": 0.5})
            lib.save({"formula": "momentum", "adjusted_score": 0.9})
            lib.save({"formula": "pe", "adjusted_score": 0.1})
            assert len(lib.load()) == 3
            top = lib.top(2)
            assert [a["formula"] for a in top] == ["momentum", "roe"]

    def test_top_uses_oos_score_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "alpha_library.json")
            lib = AlphaLibrary(path)
            lib.save({"formula": "a", "adjusted_score": 0.9})
            lib.save({"formula": "b", "oos_score": 0.99, "adjusted_score": 0.1})
            top = lib.top(1)
            assert top[0]["formula"] == "b"


# =====================================================================
# evolution/alpha_genome.py
# =====================================================================
class TestAlphaGenome:
    def test_fitness(self):
        genome = AlphaGenome(
            formula="roe",
            oos_score=0.1,
            ic=0.05,
            icir=0.5,
            complexity=3,
        )
        assert genome.fitness() == pytest.approx(
            0.1 * 0.5 + 0.05 * 0.2 + 0.5 * 0.2 - 3 * 0.01
        )

    def test_defaults(self):
        genome = AlphaGenome(formula="roe")
        assert genome.status == "EXPERIMENT"
        assert genome.generation == 0
        assert genome.fitness() == pytest.approx(0.0)


# =====================================================================
# evolution/alpha_mutation.py
# =====================================================================
class TestAlphaMutation:
    def test_zero_probability_no_change(self):
        expr = AlphaExpression(
            operator="ADD",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(operator="FEATURE", feature="pe_inverse"),
            ],
        )
        original = expr.to_string()
        out = AlphaMutation().mutate(expr, probability=0.0)
        assert out.to_string() == original

    def test_mutate_feature_node(self):
        # probability=1 forces mutation path
        expr = AlphaExpression(operator="FEATURE", feature="roe")
        out = AlphaMutation()._mutate_node(expr)
        # feature node mutated -> replaced by a random feature leaf
        assert out.operator in ("FEATURE", "CONST")
        if out.operator == "FEATURE":
            assert out.feature in FEATURES


# =====================================================================
# evolution/alpha_crossover.py
# =====================================================================
class TestAlphaCrossover:
    def test_crossover_returns_expression(self):
        parent_a = AlphaExpression(
            operator="ADD",
            children=[
                AlphaExpression(operator="FEATURE", feature="roe"),
                AlphaExpression(operator="FEATURE", feature="pe_inverse"),
            ],
        )
        parent_b = AlphaExpression(
            operator="SUB",
            children=[
                AlphaExpression(operator="FEATURE", feature="momentum_20"),
                AlphaExpression(operator="FEATURE", feature="volatility_20"),
            ],
        )
        child = AlphaCrossover().crossover(parent_a, parent_b)
        assert isinstance(child, AlphaExpression)
        assert child.operator == "ADD"
        assert len(child.children) == 2

    def test_crossover_leaf_parents(self):
        parent_a = AlphaExpression(operator="FEATURE", feature="roe")
        parent_b = AlphaExpression(operator="FEATURE", feature="pe_inverse")
        child = AlphaCrossover().crossover(parent_a, parent_b)
        assert child.children == []


# =====================================================================
# evolution/alpha_evolution.py
# =====================================================================
class TestAlphaEvolution:
    def _ranked(self, n=20):
        return [
            {
                "expression": AlphaExpression(
                    operator="ADD",
                    children=[
                        AlphaExpression(operator="FEATURE", feature="roe"),
                        AlphaExpression(operator="FEATURE", feature=f"f{i}"),
                    ],
                ),
                "adjusted_score": float(i),
            }
            for i in range(n)
        ]

    def test_evolve_empty(self):
        assert AlphaEvolution().evolve([]) == []

    def test_evolve_population_size(self):
        population = AlphaEvolution().evolve(self._ranked(), population_size=30)
        assert len(population) == 30
        assert all(isinstance(e, AlphaExpression) for e in population)


# =====================================================================
# validation/alpha_oos.py
# =====================================================================
class TestAlphaOOSValidator:
    def _data(self, n=200, seed=7):
        rng = np.random.default_rng(seed)
        roe = rng.normal(0, 1, n)
        features = pd.DataFrame({"roe": roe})
        returns = pd.Series(roe * 0.05 + rng.normal(0, 0.01, n))
        return features, returns

    def test_train_too_short(self):
        features = pd.DataFrame({"roe": [1.0, 2.0]})
        returns = pd.Series([0.01, 0.02])
        expr = AlphaExpression(operator="FEATURE", feature="roe")
        result = AlphaOOSValidator().validate(
            expr,
            AlphaEvaluator(),
            features, returns,
            features, returns,
        )
        assert result["passed"] is False
        assert result["reason"] == "TRAIN_TOO_SHORT"

    def test_pass_when_signal_holds_oos(self):
        train_f, train_r = self._data(200, seed=1)
        test_f, test_r = self._data(200, seed=2)
        expr = AlphaExpression(operator="FEATURE", feature="roe")
        result = AlphaOOSValidator().validate(
            expr,
            AlphaEvaluator(),
            train_f, train_r,
            test_f, test_r,
        )
        assert "train_ic" in result
        assert "oos_ic" in result
        # both segments have meaningful positive IC -> passed
        assert result["passed"] is True
        assert result["oos_ic"] > 0.02

    def test_returns_reason_keys(self):
        train_f, train_r = self._data(200, seed=3)
        expr = AlphaExpression(operator="FEATURE", feature="roe")
        result = AlphaOOSValidator().validate(
            expr,
            AlphaEvaluator(),
            train_f, train_r,
            train_f, train_r,
        )
        assert set(result.keys()) == {"passed", "train_ic", "oos_ic"}


# =====================================================================
# main_v39.py
# =====================================================================
class TestMainV39:
    def test_create_demo_data_shape(self):
        data, returns = main_v39.create_demo_data(n=500)
        assert isinstance(data, pd.DataFrame)
        assert isinstance(returns, pd.Series)
        assert len(data) == 500
        assert len(returns) == 500
        for col in FEATURES:
            assert col in data.columns

    def test_create_demo_data_hidden_alpha(self):
        data, returns = main_v39.create_demo_data(n=500)
        hidden = (
            data["roe"] * 0.4
            + data["momentum_20"] * 0.3
            - data["volatility_20"] * 0.2
        )
        # returns must correlate with hidden alpha
        ic = returns.corr(hidden, method="spearman")
        assert ic > 0.1
