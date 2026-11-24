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


# ============================================================
# V3.9.2 Alpha Search Engine (appended, V392 suffix)
# ============================================================

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import hashlib
import random
import time
import numpy as np
import pandas as pd

from alpha.expression import AlphaExpression  # noqa: E402
from alpha.generator import AlphaGenerator  # noqa: E402
from alpha.evaluator import AlphaEvaluator  # noqa: E402
from alpha.metrics import (  # noqa: E402
    AlphaMetricsConfigV392 as AlphaMetricsConfig,
    AlphaMetricsEngineV392 as AlphaMetricsEngine,
)
from alpha.deduplicator import (  # noqa: E402
    AlphaDeduplicatorV392,
    DeduplicationConfigV392,
)


class AlphaSearchErrorV392(Exception):
    """Alpha Search 基础异常。"""


class AlphaSearchInputErrorV392(AlphaSearchErrorV392):
    """Alpha Search 输入错误。"""


@dataclass
class AlphaSearchConfigV392:
    """
    Alpha 搜索配置。
    """
    n_candidates: int = 100
    random_seed: int = 42
    top_k: int = 20
    max_depth: int = 3
    max_nodes: int = 15
    min_obs: int = 30
    quantiles: int = 5
    min_abs_ic: float = 0.02
    min_abs_icir: float = 0.30
    min_abs_spread: float = 0.0
    complexity_penalty_weight: float = 0.002
    turnover_penalty_weight: float = 0.0
    correlation_threshold: float = 0.90
    deduplicate: bool = True
    preserve_direction: bool = True
    allow_negative_alpha: bool = True
    fail_fast: bool = False
    verbose: bool = True
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.n_candidates <= 0:
            raise ValueError("n_candidates 必须 > 0")
        if self.top_k <= 0:
            raise ValueError("top_k 必须 > 0")
        if self.top_k > self.n_candidates:
            self.top_k = self.n_candidates
        if self.max_depth <= 0:
            raise ValueError("max_depth 必须 > 0")
        if self.max_nodes <= 0:
            raise ValueError("max_nodes 必须 > 0")
        if self.min_obs < 2:
            raise ValueError("min_obs 必须 >= 2")
        if not (0.0 <= self.correlation_threshold <= 1.0):
            raise ValueError("correlation_threshold 必须位于 0~1")


@dataclass
class AlphaCandidateV392:
    """
    单个 Alpha 搜索候选。
    """
    expression: AlphaExpression
    alpha_id: str
    expression_string: str
    metrics: Dict[str, float]
    complexity: float
    score: float
    status: str = "accepted"
    rejection_reason: Optional[str] = None
    diagnostics: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        result = {
            "alpha_id": self.alpha_id,
            "expression": self.expression_string,
            "complexity": self.complexity,
            "score": self.score,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
        }
        result.update(self.metrics)
        return result


@dataclass
class AlphaSearchResultV392:
    """
    Alpha Search 总结果。
    """
    candidates: List[AlphaCandidateV392]
    accepted: List[AlphaCandidateV392]
    rejected: List[AlphaCandidateV392]
    errors: List[AlphaCandidateV392]
    diagnostics: Dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def dataframe(self) -> pd.DataFrame:
        if not self.candidates:
            return pd.DataFrame()
        return pd.DataFrame(
            [candidate.to_dict() for candidate in self.candidates]
        ).sort_values("score", ascending=False).reset_index(drop=True)

    def accepted_dataframe(self) -> pd.DataFrame:
        if not self.accepted:
            return pd.DataFrame()
        return pd.DataFrame(
            [candidate.to_dict() for candidate in self.accepted]
        ).sort_values("score", ascending=False).reset_index(drop=True)


class AlphaComplexityV392:
    """
    Alpha 公式复杂度计算。
    """

    def node_count(self, expression: AlphaExpression) -> int:
        children = getattr(expression, "children", None)
        if not children:
            return 1
        return 1 + sum(self.node_count(child) for child in children)

    def depth(self, expression: AlphaExpression) -> int:
        children = getattr(expression, "children", None)
        if not children:
            return 1
        return 1 + max(self.depth(child) for child in children)

    def operator_count(self, expression: AlphaExpression) -> int:
        children = getattr(expression, "children", None)
        count = 1
        if children:
            for child in children:
                count += self.operator_count(child)
        return count

    def score(self, expression: AlphaExpression) -> float:
        nodes = self.node_count(expression)
        depth = self.depth(expression)
        operators = self.operator_count(expression)
        return float(nodes + 0.5 * depth + 0.25 * operators)


class AlphaSearchEngineV392:
    """
    Alpha Discovery 搜索引擎。
    """

    def __init__(
        self,
        config: Optional[AlphaSearchConfigV392] = None,
        generator: Optional[AlphaGenerator] = None,
        evaluator: Optional[AlphaEvaluator] = None,
        metrics_engine: Optional[AlphaMetricsEngine] = None,
        deduplicator: Optional[AlphaDeduplicatorV392] = None,
    ):
        self.config = config or AlphaSearchConfigV392()
        self.generator = generator
        self.evaluator = evaluator
        self.metrics_engine = metrics_engine or AlphaMetricsEngine(
            AlphaMetricsConfig(
                min_obs=self.config.min_obs,
                quantiles=self.config.quantiles,
            )
        )
        self.deduplicator = deduplicator or AlphaDeduplicatorV392(
            DeduplicationConfigV392(
                min_obs=self.config.min_obs,
                correlation_threshold=self.config.correlation_threshold,
            )
        )
        self.complexity = AlphaComplexityV392()
        self.rng = random.Random(self.config.random_seed)

    def expression_string(self, expression: AlphaExpression) -> str:
        for method_name in ["to_string", "serialize"]:
            method = getattr(expression, method_name, None)
            if callable(method):
                try:
                    value = method()
                    if value:
                        return str(value)
                except Exception:
                    pass
        return repr(expression)

    def alpha_id(self, expression: AlphaExpression) -> str:
        existing = getattr(expression, "alpha_id", None)
        if existing:
            return str(existing)
        expression_string = self.expression_string(expression)
        digest = hashlib.sha256(expression_string.encode("utf-8")).hexdigest()
        return "alpha_" + digest[:16]

    def generate_candidates(
        self,
        factors: Optional[Sequence[str]] = None,
        generator_kwargs: Optional[Dict] = None,
    ) -> List[AlphaExpression]:
        if self.generator is None:
            raise AlphaSearchErrorV392(
                "AlphaSearchEngine 没有配置 AlphaGenerator"
            )
        kwargs = dict(generator_kwargs) if generator_kwargs else {}
        kwargs.setdefault("n", self.config.n_candidates)
        kwargs.setdefault("max_depth", self.config.max_depth)
        kwargs.setdefault("max_nodes", self.config.max_nodes)
        if factors is not None:
            kwargs.setdefault("features", list(factors))

        for method_name in ["generate", "generate_candidates", "sample"]:
            method = getattr(self.generator, method_name, None)
            if not callable(method):
                continue
            try:
                result = method(**kwargs)
                if result is None:
                    continue
                return list(result)
            except TypeError:
                try:
                    result = method(self.config.n_candidates)
                    if result is not None:
                        return list(result)
                except TypeError:
                    continue
        raise AlphaSearchErrorV392(
            "无法调用 AlphaGenerator。请检查 generator.py 的 generate API。"
        )

    def evaluate_expression(
        self,
        expression: AlphaExpression,
        data: pd.DataFrame,
    ) -> pd.Series:
        if self.evaluator is None:
            raise AlphaSearchErrorV392(
                "AlphaSearchEngine 没有配置 AlphaEvaluator"
            )

        for method_name in ["evaluate", "run", "compute"]:
            method = getattr(self.evaluator, method_name, None)
            if not callable(method):
                continue
            attempts = [
                lambda: method(expression, data),
                lambda: method(data, expression),
                lambda: method(expression=expression, data=data),
                lambda: method(data=data, expression=expression),
            ]
            for attempt in attempts:
                try:
                    result = attempt()
                    if isinstance(result, pd.Series):
                        return result
                    if isinstance(result, pd.DataFrame):
                        if "signal" in result.columns:
                            return result["signal"]
                        if expression in result.columns:
                            return result[expression]
                except (TypeError, KeyError, AttributeError):
                    continue
        raise AlphaSearchErrorV392(
            "无法调用 AlphaEvaluator。请检查 evaluator.py API。"
        )

    def attach_signal(
        self,
        data: pd.DataFrame,
        signal: pd.Series,
    ) -> pd.DataFrame:
        df = data.copy()
        if len(signal) == len(df):
            try:
                if signal.index.equals(df.index):
                    df["signal"] = pd.to_numeric(signal, errors="coerce")
                    return df
            except Exception:
                pass

        if isinstance(signal.index, pd.MultiIndex):
            if "date" in df.columns and "code" in df.columns:
                index = pd.MultiIndex.from_frame(
                    df[["date", "code"]]
                )
                mapped = pd.Series(
                    signal.to_numpy(),
                    index=signal.index,
                )
                df["signal"] = index.map(mapped)
                return df

        if len(signal) == len(df):
            df["signal"] = pd.to_numeric(
                signal.to_numpy(), errors="coerce"
            )
            return df

        raise AlphaSearchInputErrorV392(
            "Evaluator 返回的 signal 无法与输入 data 对齐"
        )

    def evaluate_metrics(
        self,
        signal_data: pd.DataFrame,
    ) -> Tuple[Dict[str, float], object]:
        result = self.metrics_engine.compute(signal_data)
        return result.summary, result

    def calculate_score(
        self,
        metrics: Dict[str, float],
        complexity: float,
    ) -> float:
        ic = metrics.get("ic_mean", np.nan)
        icir = metrics.get("ic_ir", np.nan)
        spread = metrics.get("high_low_mean", np.nan)
        turnover = metrics.get("turnover_mean", np.nan)

        if not np.isfinite(ic):
            return -np.inf
        if not np.isfinite(icir):
            icir = 0.0
        if not np.isfinite(spread):
            spread = 0.0
        if not np.isfinite(turnover):
            turnover = 0.0

        score = ic + 0.10 * icir + 0.50 * spread
        score -= self.config.complexity_penalty_weight * complexity
        score -= self.config.turnover_penalty_weight * turnover
        return float(score)

    def acceptance_check(
        self,
        metrics: Dict[str, float],
    ) -> Tuple[bool, Optional[str]]:
        ic = metrics.get("ic_mean", np.nan)
        icir = metrics.get("ic_ir", np.nan)
        spread = metrics.get("high_low_mean", np.nan)

        if not np.isfinite(ic):
            return (False, "invalid_ic")
        if (
            not self.config.allow_negative_alpha
            and ic < 0
        ):
            return (False, "negative_ic")
        if (
            abs(ic) < self.config.min_abs_ic
        ):
            return (False, "ic_below_threshold")

        if (
            np.isfinite(icir)
            and abs(icir) < self.config.min_abs_icir
        ):
            return (False, "icir_below_threshold")

        if np.isfinite(spread):
            if (
                abs(spread) < self.config.min_abs_spread
            ):
                return (False, "quantile_spread_below_threshold")

        return (True, None)

    def evaluate_candidate(
        self,
        expression: AlphaExpression,
        data: pd.DataFrame,
    ) -> AlphaCandidateV392:
        alpha_id = self.alpha_id(expression)
        expression_string = self.expression_string(expression)
        complexity = self.complexity.score(expression)

        try:
            signal = self.evaluate_expression(expression, data)
            signal_data = self.attach_signal(data, signal)
            metrics, metric_result = self.evaluate_metrics(signal_data)
            accepted, reason = self.acceptance_check(metrics)
            score = self.calculate_score(metrics, complexity)
            status = "accepted" if accepted else "rejected"
            return AlphaCandidateV392(
                expression=expression,
                alpha_id=alpha_id,
                expression_string=expression_string,
                metrics=metrics,
                complexity=complexity,
                score=score,
                status=status,
                rejection_reason=reason,
                diagnostics={
                    "metric_diagnostics": metric_result.diagnostics,
                },
            )
        except Exception as exc:
            if self.config.fail_fast:
                raise
            return AlphaCandidateV392(
                expression=expression,
                alpha_id=alpha_id,
                expression_string=expression_string,
                metrics={},
                complexity=complexity,
                score=-np.inf,
                status="error",
                rejection_reason=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    def search(
        self,
        data: pd.DataFrame,
        factors: Optional[Sequence[str]] = None,
        candidates: Optional[Sequence[AlphaExpression]] = None,
        generator_kwargs: Optional[Dict] = None,
    ) -> AlphaSearchResultV392:
        start_time = time.time()

        if not isinstance(data, pd.DataFrame):
            raise AlphaSearchInputErrorV392("data 必须是 pandas.DataFrame")
        if data.empty:
            raise AlphaSearchInputErrorV392("data 不能为空")

        if candidates is None:
            expressions = self.generate_candidates(
                factors=factors,
                generator_kwargs=generator_kwargs,
            )
        else:
            expressions = list(candidates)

        expressions = expressions[: self.config.n_candidates]
        if not expressions:
            raise AlphaSearchErrorV392("没有生成任何 Alpha candidate")

        candidate_results = []
        for index, expression in enumerate(expressions, start=1):
            if self.config.verbose:
                print(
                    f"[Alpha Search] "
                    f"{index}/{len(expressions)}"
                )
            result = self.evaluate_candidate(expression, data)
            candidate_results.append(result)

        valid_candidates = [
            candidate
            for candidate in candidate_results
            if candidate.status in {"accepted", "rejected"}
        ]

        rejected_by_dedup = []
        if (
            self.config.deduplicate
            and valid_candidates
        ):
            expressions = [
                candidate.expression
                for candidate in valid_candidates
            ]
            signal_map = {}
            for candidate in valid_candidates:
                try:
                    signal = self.evaluate_expression(
                        candidate.expression, data
                    )
                    signal_data = self.attach_signal(data, signal)
                    if (
                        "date" in signal_data.columns
                        and "code" in signal_data.columns
                    ):
                        index = pd.MultiIndex.from_frame(
                            signal_data[["date", "code"]]
                        )
                        signal_series = pd.Series(
                            signal_data["signal"].to_numpy(),
                            index=index,
                        )
                    else:
                        signal_series = pd.Series(
                            signal_data["signal"].to_numpy()
                        )
                    signal_map[candidate.alpha_id] = signal_series
                except Exception:
                    continue

            dedup_result = self.deduplicator.deduplicate(
                expressions,
                signals=signal_map,
            )
            accepted_ids = {
                self.alpha_id(expression)
                for expression in dedup_result.accepted
            }
            for candidate in valid_candidates:
                if (
                    candidate.alpha_id not in accepted_ids
                ):
                    candidate.status = "rejected"
                    candidate.rejection_reason = "duplicate_alpha"
                    rejected_by_dedup.append(candidate)

        accepted = [
            candidate
            for candidate in candidate_results
            if candidate.status == "accepted"
        ]
        rejected = [
            candidate
            for candidate in candidate_results
            if candidate.status == "rejected"
        ]
        errors = [
            candidate
            for candidate in candidate_results
            if candidate.status == "error"
        ]

        accepted.sort(key=lambda x: x.score, reverse=True)
        accepted = accepted[: self.config.top_k]

        elapsed = time.time() - start_time

        diagnostics = {
            "requested_candidates": self.config.n_candidates,
            "generated_candidates": len(expressions),
            "evaluated_candidates": len(candidate_results),
            "accepted_before_top_k": len(
                [
                    c
                    for c in candidate_results
                    if c.status == "accepted"
                ]
            ),
            "final_accepted": len(accepted),
            "rejected": len(rejected),
            "errors": len(errors),
            "random_seed": self.config.random_seed,
            "max_depth": self.config.max_depth,
            "max_nodes": self.config.max_nodes,
            "dedup_enabled": self.config.deduplicate,
            "correlation_threshold": self.config.correlation_threshold,
        }

        return AlphaSearchResultV392(
            candidates=candidate_results,
            accepted=accepted,
            rejected=rejected,
            errors=errors,
            diagnostics=diagnostics,
            elapsed_seconds=elapsed,
        )


def search_alphas_v392(
    data: pd.DataFrame,
    generator: AlphaGenerator,
    evaluator: AlphaEvaluator,
    config: Optional[AlphaSearchConfigV392] = None,
    factors: Optional[Sequence[str]] = None,
    candidates: Optional[Sequence[AlphaExpression]] = None,
) -> AlphaSearchResultV392:
    engine = AlphaSearchEngineV392(
        config=config,
        generator=generator,
        evaluator=evaluator,
    )
    return engine.search(
        data=data,
        factors=factors,
        candidates=candidates,
    )


def _build_feature_v392(feature: str) -> AlphaExpression:
    return AlphaExpression(
        operator="feature",
        children=[],
        feature=feature,
    )


def _build_binary_v392(
    operator: str,
    left: AlphaExpression,
    right: AlphaExpression,
) -> AlphaExpression:
    return AlphaExpression(
        operator=operator,
        children=[left, right],
    )


class _MockGeneratorV392:
    """
    Self-test 使用的最小 Generator。
    """

    def __init__(self, expressions):
        self.expressions = expressions

    def generate(self, **kwargs):
        n = kwargs.get("n", len(self.expressions))
        return self.expressions[:n]


class _MockEvaluatorV392:
    """
    Self-test 使用的 evaluator。
    """

    def evaluate(self, expression, data):
        feature = getattr(expression, "feature", None)
        if feature is not None:
            return data[feature]
        operator = str(
            getattr(expression, "operator", "")
        ).lower()
        children = getattr(expression, "children", [])
        if operator in {"add", "+"}:
            return (
                self.evaluate(children[0], data)
                + self.evaluate(children[1], data)
            )
        if operator in {"sub", "-"}:
            return (
                self.evaluate(children[0], data)
                - self.evaluate(children[1], data)
            )
        raise ValueError(f"Mock evaluator 不支持: {operator}")


def _self_test_v392():
    print("Running alpha.search self-test...")

    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    codes = [f"{i:06d}" for i in range(60)]
    records = []
    for date in dates:
        momentum = rng.normal(0, 1, len(codes))
        roe = rng.normal(0, 1, len(codes))
        noise = rng.normal(0, 1, len(codes))
        forward_return = momentum * 0.03 + noise * 0.005
        for code, m, r, ret in zip(codes, momentum, roe, forward_return):
            records.append(
                {
                    "date": date,
                    "code": code,
                    "momentum_20": m,
                    "roe": r,
                    "forward_return": ret,
                }
            )
    data = pd.DataFrame(records)

    momentum = _build_feature_v392("momentum_20")
    roe = _build_feature_v392("roe")
    alpha_momentum = momentum
    alpha_roe = roe
    alpha_mix = _build_binary_v392("add", momentum, roe)
    alpha_mix_duplicate = _build_binary_v392("add", roe, momentum)

    expressions = [
        alpha_momentum,
        alpha_roe,
        alpha_mix,
        alpha_mix_duplicate,
    ]

    generator = _MockGeneratorV392(expressions)
    evaluator = _MockEvaluatorV392()

    config = AlphaSearchConfigV392(
        n_candidates=4,
        top_k=3,
        min_obs=30,
        min_abs_ic=0.02,
        min_abs_icir=0.0,
        correlation_threshold=0.95,
        deduplicate=True,
        verbose=False,
        random_seed=42,
    )

    engine = AlphaSearchEngineV392(
        config=config,
        generator=generator,
        evaluator=evaluator,
    )

    result = engine.search(data)

    print("\n=== Search Diagnostics ===")
    print(result.diagnostics)
    print("\n=== Accepted ===")
    if result.accepted:
        print(
            result.accepted_dataframe().to_string(index=False)
        )
    else:
        print("No accepted Alpha.")

    assert any(
        candidate.metrics.get("ic_mean", 0) > 0.02
        for candidate in result.candidates
        if candidate.metrics
    )
    assert result.diagnostics["evaluated_candidates"] == 4
    assert len(result.accepted) >= 1

    print("\nalpha.search self-test PASSED.")


if __name__ == "__main__":
    _self_test_v392()
