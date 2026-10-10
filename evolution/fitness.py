"""
AI Hedge Fund OS - V3.9.3
File: evolution/fitness.py
Alpha fitness scoring, penalties, and acceptance checks.
Python: 3.11+
Design principles
-----------------
1. Consume metrics produced by the existing research/backtest pipeline.
2. Never fabricate IC, ICIR, returns, or OOS results.
3. Preserve the direction of alpha metrics; never use abs(IC) as a shortcut.
4. Keep fitness scoring separate from OOS acceptance.
5. Penalize excessive turnover, complexity, and signal correlation.
6. Treat missing/non-finite metrics explicitly.
7. Do not connect to brokers or expose live-trading interfaces.
"""
from __future__ import annotations
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional
# V3.9.3 fitness 基于项目的 AlphaGenomeV393（具备 ic/icir/oos 等指标字段）。
from evolution.alpha_genome import (
    AlphaGenomeV393 as AlphaGenome,
)
class AlphaFitnessError(RuntimeError):
    """Base exception for Alpha fitness evaluation."""
class MissingFitnessMetricsError(AlphaFitnessError):
    """Raised when required metrics are unavailable."""
class InvalidFitnessMetricsError(AlphaFitnessError):
    """Raised when supplied metrics have invalid values."""
@dataclass
class AlphaFitnessConfig:
    """Configuration for fitness scoring and acceptance."""
    # Metric weights. Weights are normalized during initialization.
    weight_ic: float = 0.30
    weight_icir: float = 0.20
    weight_quantile_spread: float = 0.20
    weight_long_short_spread: float = 0.10
    weight_hit_rate: float = 0.10
    weight_oos: float = 0.10
    # Metric scales used by the bounded transformation tanh(x / scale).
    # These are scaling parameters, not claimed market performance.
    ic_scale: float = 0.03
    icir_scale: float = 1.00
    quantile_spread_scale: float = 0.03
    long_short_spread_scale: float = 0.03
    oos_ic_scale: float = 0.03
    oos_icir_scale: float = 1.00
    oos_spread_scale: float = 0.03
    # Penalty coefficients. All metrics should use consistent units.
    turnover_penalty: float = 0.10
    complexity_penalty: float = 0.01
    correlation_penalty: float = 0.10
    drawdown_penalty: float = 0.10
    volatility_penalty: float = 0.00
    # Optional hard acceptance gates.
    min_ic: Optional[float] = None
    min_icir: Optional[float] = None
    min_quantile_spread: Optional[float] = None
    max_turnover: Optional[float] = None
    max_complexity: Optional[float] = None
    max_correlation: Optional[float] = None
    max_drawdown: Optional[float] = None
    # OOS is kept separate from training fitness by default.
    require_oos_for_acceptance: bool = True
    require_positive_oos_ic: bool = True
    min_oos_ic: Optional[float] = None
    min_oos_icir: Optional[float] = None
    min_oos_quantile_spread: Optional[float] = None
    max_oos_turnover: Optional[float] = None
    # Missing metrics policy.
    # If True, absent metrics contribute zero and are reported as missing.
    # If False, missing core metrics prevent a valid fitness result.
    allow_missing_metrics: bool = True
    # A finite score must be produced to mark a genome evaluated.
    min_fitness: Optional[float] = None
    # Used only for explicit numeric validation.
    epsilon: float = 1e-12
    def __post_init__(self) -> None:
        weight_names = (
            "weight_ic",
            "weight_icir",
            "weight_quantile_spread",
            "weight_long_short_spread",
            "weight_hit_rate",
            "weight_oos",
        )
        for name in weight_names:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
            setattr(self, name, value)
        if sum(getattr(self, name) for name in weight_names) <= 0:
            raise ValueError("At least one fitness weight must be positive")
        scales = (
            "ic_scale",
            "icir_scale",
            "quantile_spread_scale",
            "long_short_spread_scale",
            "oos_ic_scale",
            "oos_icir_scale",
            "oos_spread_scale",
        )
        for name in scales:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
        penalties = (
            "turnover_penalty",
            "complexity_penalty",
            "correlation_penalty",
            "drawdown_penalty",
            "volatility_penalty",
        )
        for name in penalties:
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        for name in (
            "min_ic",
            "min_icir",
            "min_quantile_spread",
            "max_turnover",
            "max_complexity",
            "max_correlation",
            "max_drawdown",
            "min_oos_ic",
            "min_oos_icir",
            "min_oos_quantile_spread",
            "max_oos_turnover",
            "min_fitness",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite when provided")
        if self.epsilon <= 0:
            raise ValueError("epsilon must be > 0")
    def normalized_weights(self) -> dict[str, float]:
        """Return weights normalized to sum to one."""
        raw = {
            "ic": self.weight_ic,
            "icir": self.weight_icir,
            "quantile_spread": self.weight_quantile_spread,
            "long_short_spread": self.weight_long_short_spread,
            "hit_rate": self.weight_hit_rate,
            "oos": self.weight_oos,
        }
        total = sum(raw.values())
        return {key: value / total for key, value in raw.items()}
@dataclass
class FitnessResult:
    """Detailed, auditable result for one Alpha fitness evaluation."""
    genome_id: str
    fitness: Optional[float]
    valid: bool
    component_scores: dict[str, Optional[float]] = field(default_factory=dict)
    weighted_score: Optional[float] = None
    penalties: dict[str, float] = field(default_factory=dict)
    penalty_total: float = 0.0
    missing_metrics: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    oos_available: bool = False
    oos_passed: Optional[bool] = None
    accepted: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
def _finite_number(
    value: Any,
    *,
    field_name: str,
    allow_none: bool = True,
) -> Optional[float]:
    """Convert a value to a finite float without silently accepting NaN."""
    if value is None:
        if allow_none:
            return None
        raise MissingFitnessMetricsError(
            f"Required metric '{field_name}' is missing"
        )
    if isinstance(value, bool):
        raise InvalidFitnessMetricsError(
            f"Metric '{field_name}' must be numeric, not bool"
        )
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidFitnessMetricsError(
            f"Metric '{field_name}' is not numeric: {value!r}"
        ) from exc
    if not math.isfinite(number):
        raise InvalidFitnessMetricsError(
            f"Metric '{field_name}' must be finite"
        )
    return number
def _bounded_score(value: Optional[float], scale: float) -> Optional[float]:
    """
    Transform a signed metric into [-1, 1].
    Positive and negative values retain their direction. This avoids
    rewarding a strongly negative IC simply because its absolute value is high.
    """
    if value is None:
        return None
    return math.tanh(value / scale)
def _hit_rate_score(value: Optional[float]) -> Optional[float]:
    """
    Map a hit rate in [0, 1] to [-1, 1], centered at 0.5.
    A hit rate of 0.5 contributes zero. A hit rate below 0.5 is negative.
    """
    if value is None:
        return None
    if not 0.0 <= value <= 1.0:
        raise InvalidFitnessMetricsError(
            f"hit_rate must be between 0 and 1; received {value}"
        )
    return 2.0 * value - 1.0
def _unit_interval(
    value: Optional[float],
    *,
    field_name: str,
) -> Optional[float]:
    """Validate a metric that must be between zero and one."""
    if value is None:
        return None
    if not 0.0 <= value <= 1.0:
        raise InvalidFitnessMetricsError(
            f"{field_name} must be between 0 and 1; received {value}"
        )
    return value
class AlphaFitnessEvaluator:
    """
    Calculate a composite Alpha fitness score from externally computed metrics.
    Accepted input:
    - An AlphaGenome whose metric attributes have already been populated.
    - An explicit metrics mapping from the research/evaluation pipeline.
    This class does not run a backtest and does not calculate IC from raw data.
    """
    CORE_METRICS = (
        "ic",
        "icir",
        "quantile_spread",
        "long_short_spread",
        "hit_rate",
    )
    def __init__(
        self,
        config: Optional[AlphaFitnessConfig] = None,
    ) -> None:
        self.config = config or AlphaFitnessConfig()
        self.weights = self.config.normalized_weights()
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(
        self,
        genome: AlphaGenome,
        metrics: Optional[Mapping[str, Any]] = None,
        oos_metrics: Optional[Mapping[str, Any]] = None,
        *,
        apply_to_genome: bool = True,
    ) -> FitnessResult:
        """
        Score one genome.
        The metrics argument takes precedence over genome attributes.
        OOS metrics can be supplied separately; absent OOS data is not
        interpreted as a successful validation.
        """
        if not isinstance(genome, AlphaGenome):
            raise TypeError("genome must be an AlphaGenome")
        training = self._collect_metrics(genome, metrics)
        oos = self._collect_oos_metrics(genome, oos_metrics)
        missing = [
            name for name in self.CORE_METRICS
            if training.get(name) is None
        ]
        if missing and not self.config.allow_missing_metrics:
            raise MissingFitnessMetricsError(
                "Missing core metrics: " + ", ".join(missing)
            )
        component_scores = self._component_scores(training, oos)
        weighted_score = self._weighted_score(component_scores)
        penalties = self._calculate_penalties(genome, training)
        penalty_total = sum(penalties.values())
        fitness = weighted_score - penalty_total
        if not math.isfinite(fitness):
            raise InvalidFitnessMetricsError(
                "Fitness calculation produced a non-finite value"
            )
        failed_checks = self._training_gate_failures(genome, training)
        oos_available = self._has_oos_data(oos)
        oos_passed: Optional[bool]
        if not oos_available:
            oos_passed = None
        else:
            oos_passed = len(self._oos_gate_failures(oos)) == 0
        # Acceptance is deliberately stricter than having a high score.
        accepted = not failed_checks
        if self.config.require_oos_for_acceptance:
            accepted = accepted and oos_passed is True
        elif oos_passed is False:
            # If OOS results exist and fail, do not accept the Alpha.
            accepted = False
        if (
            self.config.min_fitness is not None
            and fitness < self.config.min_fitness
        ):
            failed_checks.append("fitness_below_minimum")
            accepted = False
        result = FitnessResult(
            genome_id=str(genome.genome_id),
            fitness=fitness,
            valid=True,
            component_scores=component_scores,
            weighted_score=weighted_score,
            penalties=penalties,
            penalty_total=penalty_total,
            missing_metrics=missing,
            failed_checks=failed_checks,
            oos_available=oos_available,
            oos_passed=oos_passed,
            accepted=accepted,
            details={
                "training_metrics": training,
                "oos_metrics": oos,
                "weights": dict(self.weights),
                "config": asdict(self.config),
                "scoring_note": (
                    "Fitness is a research-ranking score, not an expected "
                    "return, probability of profit, or trading recommendation."
                ),
            },
        )
        if apply_to_genome:
            self._apply_result(genome, result, training, oos)
        return result
    def evaluate_many(
        self,
        genomes: list[AlphaGenome],
        metrics_by_genome: Optional[
            Mapping[str, Mapping[str, Any]]
        ] = None,
        oos_by_genome: Optional[
            Mapping[str, Mapping[str, Any]]
        ] = None,
    ) -> list[FitnessResult]:
        """Evaluate multiple genomes using caller-provided metric mappings."""
        metrics_by_genome = metrics_by_genome or {}
        oos_by_genome = oos_by_genome or {}
        results: list[FitnessResult] = []
        for genome in genomes:
            key = str(genome.genome_id)
            result = self.evaluate(
                genome,
                metrics=metrics_by_genome.get(key),
                oos_metrics=oos_by_genome.get(key),
            )
            results.append(result)
        return results
    def acceptance_check(
        self,
        genome: AlphaGenome,
        metrics: Optional[Mapping[str, Any]] = None,
        oos_metrics: Optional[Mapping[str, Any]] = None,
    ) -> FitnessResult:
        """Explicit alias emphasizing the acceptance decision."""
        return self.evaluate(
            genome,
            metrics=metrics,
            oos_metrics=oos_metrics,
            apply_to_genome=False,
        )
    # ------------------------------------------------------------------
    # Metric collection and validation
    # ------------------------------------------------------------------
    def _collect_metrics(
        self,
        genome: AlphaGenome,
        supplied: Optional[Mapping[str, Any]],
    ) -> dict[str, Optional[float]]:
        source: dict[str, Any] = {
            "ic": getattr(genome, "ic", None),
            "icir": getattr(genome, "icir", None),
            "quantile_spread": getattr(genome, "quantile_spread", None),
            "long_short_spread": getattr(genome, "long_short_spread", None),
            "hit_rate": getattr(genome, "hit_rate", None),
            "turnover": getattr(genome, "turnover", None),
            "volatility": getattr(genome, "volatility", None),
            "max_drawdown": getattr(genome, "max_drawdown", None),
            "max_correlation": getattr(genome, "max_correlation", None),
            "mean_correlation": getattr(genome, "mean_correlation", None),
            "correlation_penalty": getattr(
                genome, "correlation_penalty", None
            ),
            "complexity": getattr(genome, "complexity", None),
            "node_count": getattr(genome, "node_count", None),
        }
        if supplied is not None:
            source.update(dict(supplied))
        normalized: dict[str, Optional[float]] = {}
        for name, value in source.items():
            # AlphaGenomeV393 未评估字段默认值为 NaN，等价于“缺失”。
            # 显式通过 metrics 传入的 NaN 仍按无效值报错。
            if (
                supplied is None or name not in supplied
            ) and isinstance(value, float) and math.isnan(value):
                normalized[name] = None
                continue
            normalized[name] = _finite_number(
                value,
                field_name=name,
                allow_none=True,
            )
        if normalized.get("hit_rate") is not None:
            _unit_interval(
                normalized["hit_rate"],
                field_name="hit_rate",
            )
        return normalized
    def _collect_oos_metrics(
        self,
        genome: AlphaGenome,
        supplied: Optional[Mapping[str, Any]],
    ) -> dict[str, Optional[float]]:
        source: dict[str, Any] = {
            "oos_ic": getattr(genome, "oos_ic", None),
            "oos_icir": getattr(genome, "oos_icir", None),
            "oos_quantile_spread": getattr(
                genome, "oos_quantile_spread", None
            ),
            "oos_turnover": getattr(genome, "oos_turnover", None),
            "oos_passed": getattr(genome, "oos_passed", None),
        }
        if supplied is not None:
            source.update(dict(supplied))
        normalized: dict[str, Optional[float]] = {}
        for name, value in source.items():
            if name == "oos_passed":
                if value is None:
                    normalized[name] = None
                elif supplied is not None and name in supplied:
                    if isinstance(value, bool):
                        normalized[name] = 1.0 if value else 0.0
                    else:
                        raise InvalidFitnessMetricsError(
                            "oos_passed must be bool or None"
                        )
                else:
                    # AlphaGenomeV393 默认 oos_passed=False 表示“未验证”，
                    # 不视为显式 OOS 失败；仅显式传入的 oos_passed 参与判定。
                    normalized[name] = None
                continue
            if (
                supplied is None or name not in supplied
            ) and isinstance(value, float) and math.isnan(value):
                normalized[name] = None
                continue
            normalized[name] = _finite_number(
                value,
                field_name=name,
                allow_none=True,
            )
        return normalized
    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _component_scores(
        self,
        training: Mapping[str, Optional[float]],
        oos: Mapping[str, Optional[float]],
    ) -> dict[str, Optional[float]]:
        ic_score = _bounded_score(
            training.get("ic"), self.config.ic_scale
        )
        icir_score = _bounded_score(
            training.get("icir"), self.config.icir_scale
        )
        q_score = _bounded_score(
            training.get("quantile_spread"),
            self.config.quantile_spread_scale,
        )
        ls_score = _bounded_score(
            training.get("long_short_spread"),
            self.config.long_short_spread_scale,
        )
        hit_score = _hit_rate_score(training.get("hit_rate"))
        oos_parts: list[float] = []
        oos_ic = oos.get("oos_ic")
        oos_icir = oos.get("oos_icir")
        oos_spread = oos.get("oos_quantile_spread")
        if oos_ic is not None:
            oos_parts.append(
                _bounded_score(oos_ic, self.config.oos_ic_scale) or 0.0
            )
        if oos_icir is not None:
            oos_parts.append(
                _bounded_score(oos_icir, self.config.oos_icir_scale) or 0.0
            )
        if oos_spread is not None:
            oos_parts.append(
                _bounded_score(
                    oos_spread, self.config.oos_spread_scale
                ) or 0.0
            )
        # Do not infer successful OOS from missing OOS metrics.
        oos_score = (
            sum(oos_parts) / len(oos_parts)
            if oos_parts
            else None
        )
        return {
            "ic": ic_score,
            "icir": icir_score,
            "quantile_spread": q_score,
            "long_short_spread": ls_score,
            "hit_rate": hit_score,
            "oos": oos_score,
        }
    def _weighted_score(
        self,
        component_scores: Mapping[str, Optional[float]],
    ) -> float:
        """
        Weighted score with missing components omitted and remaining weights
        renormalized. This does not convert missing data into a positive score.
        """
        numerator = 0.0
        denominator = 0.0
        for name, weight in self.weights.items():
            score = component_scores.get(name)
            if score is None or weight <= 0:
                continue
            numerator += weight * score
            denominator += weight
        if denominator <= self.config.epsilon:
            raise MissingFitnessMetricsError(
                "No usable metric is available for fitness calculation"
            )
        return numerator / denominator
    def _calculate_penalties(
        self,
        genome: AlphaGenome,
        metrics: Mapping[str, Optional[float]],
    ) -> dict[str, float]:
        penalties: dict[str, float] = {}
        turnover = metrics.get("turnover")
        if turnover is not None:
            if turnover < 0:
                raise InvalidFitnessMetricsError(
                    "turnover must be >= 0"
                )
            penalties["turnover"] = (
                self.config.turnover_penalty * turnover
            )
        else:
            penalties["turnover"] = 0.0
        complexity = metrics.get("complexity")
        if complexity is None:
            complexity = metrics.get("node_count")
        if complexity is not None:
            if complexity < 0:
                raise InvalidFitnessMetricsError(
                    "complexity must be >= 0"
                )
            penalties["complexity"] = (
                self.config.complexity_penalty * complexity
            )
        else:
            penalties["complexity"] = 0.0
        correlation_penalty = metrics.get("correlation_penalty")
        if correlation_penalty is None:
            max_corr = metrics.get("max_correlation")
            if max_corr is not None:
                # Correlation penalty applies only to positive redundancy.
                correlation_penalty = max(0.0, max_corr)
        if correlation_penalty is not None:
            if correlation_penalty < 0:
                raise InvalidFitnessMetricsError(
                    "correlation_penalty must be >= 0"
                )
            penalties["correlation"] = (
                self.config.correlation_penalty * correlation_penalty
            )
        else:
            penalties["correlation"] = 0.0
        drawdown = metrics.get("max_drawdown")
        if drawdown is not None:
            # Accept common drawdown conventions:
            # -0.20 for a 20% drawdown, or 0.20 as drawdown magnitude.
            drawdown_magnitude = abs(drawdown)
            if drawdown_magnitude > 1.0:
                raise InvalidFitnessMetricsError(
                    "max_drawdown magnitude must not exceed 1.0"
                )
            penalties["drawdown"] = (
                self.config.drawdown_penalty * drawdown_magnitude
            )
        else:
            penalties["drawdown"] = 0.0
        volatility = metrics.get("volatility")
        if volatility is not None:
            if volatility < 0:
                raise InvalidFitnessMetricsError(
                    "volatility must be >= 0"
                )
            penalties["volatility"] = (
                self.config.volatility_penalty * volatility
            )
        else:
            penalties["volatility"] = 0.0
        return penalties
    # ------------------------------------------------------------------
    # Hard acceptance checks
    # ------------------------------------------------------------------
    def _training_gate_failures(
        self,
        genome: AlphaGenome,
        metrics: Mapping[str, Optional[float]],
    ) -> list[str]:
        failures: list[str] = []
        checks = (
            ("min_ic", "ic", lambda x, t: x >= t),
            ("min_icir", "icir", lambda x, t: x >= t),
            (
                "min_quantile_spread",
                "quantile_spread",
                lambda x, t: x >= t,
            ),
            ("max_turnover", "turnover", lambda x, t: x <= t),
            ("max_complexity", "complexity", lambda x, t: x <= t),
            (
                "max_correlation",
                "max_correlation",
                lambda x, t: x <= t,
            ),
        )
        for config_name, metric_name, comparator in checks:
            threshold = getattr(self.config, config_name)
            if threshold is None:
                continue
            value = metrics.get(metric_name)
            if value is None:
                failures.append(f"missing_{metric_name}")
            elif not comparator(value, threshold):
                failures.append(f"{metric_name}_failed_threshold")
        max_drawdown = self.config.max_drawdown
        if max_drawdown is not None:
            value = metrics.get("max_drawdown")
            if value is None:
                failures.append("missing_max_drawdown")
            elif abs(value) > max_drawdown:
                failures.append("max_drawdown_failed_threshold")
        # The expression must still satisfy the configured structural limits.
        try:
            genome.expression.validate()
        except (ValueError, TypeError, AttributeError):
            failures.append("invalid_expression")
        return failures
    def _oos_gate_failures(
        self,
        oos: Mapping[str, Optional[float]],
    ) -> list[str]:
        failures: list[str] = []
        if oos.get("oos_passed") == 0.0:
            failures.append("oos_explicitly_failed")
        checks = (
            ("min_oos_ic", "oos_ic", lambda x, t: x >= t),
            ("min_oos_icir", "oos_icir", lambda x, t: x >= t),
            (
                "min_oos_quantile_spread",
                "oos_quantile_spread",
                lambda x, t: x >= t,
            ),
            (
                "max_oos_turnover",
                "oos_turnover",
                lambda x, t: x <= t,
            ),
        )
        for config_name, metric_name, comparator in checks:
            threshold = getattr(self.config, config_name)
            if threshold is None:
                continue
            value = oos.get(metric_name)
            if value is None:
                failures.append(f"missing_{metric_name}")
            elif not comparator(value, threshold):
                failures.append(f"{metric_name}_failed_threshold")
        if self.config.require_positive_oos_ic:
            value = oos.get("oos_ic")
            if value is None:
                failures.append("missing_oos_ic")
            elif value <= 0:
                failures.append("oos_ic_not_positive")
        return failures
    @staticmethod
    def _has_oos_data(
        oos: Mapping[str, Optional[float]],
    ) -> bool:
        return any(
            oos.get(key) is not None
            for key in (
                "oos_ic",
                "oos_icir",
                "oos_quantile_spread",
            )
        )
    # ------------------------------------------------------------------
    # Apply result to genome
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_result(
        genome: AlphaGenome,
        result: FitnessResult,
        training: Mapping[str, Optional[float]],
        oos: Mapping[str, Optional[float]],
    ) -> None:
        """
        Store only supplied/calculated metrics and the resulting fitness.
        Genome.update_fitness signatures can vary across project revisions,
        so direct assignment is used for the known V3.9.3 fields.
        """
        genome.fitness = (
            result.fitness
            if result.fitness is not None
            else float("-inf")
        )
        for name in (
            "ic",
            "icir",
            "quantile_spread",
            "long_short_spread",
            "hit_rate",
            "turnover",
            "volatility",
            "max_drawdown",
            "max_correlation",
            "mean_correlation",
            "correlation_penalty",
        ):
            value = training.get(name)
            if value is not None and hasattr(genome, name):
                setattr(genome, name, value)
        for name in (
            "oos_ic",
            "oos_icir",
            "oos_quantile_spread",
            "oos_turnover",
        ):
            value = oos.get(name)
            if value is not None and hasattr(genome, name):
                setattr(genome, name, value)
        # Do not silently set genome.oos_passed=True just because metrics exist.
        if oos.get("oos_passed") is not None:
            genome.oos_passed = bool(oos["oos_passed"])
        genome.metadata = dict(getattr(genome, "metadata", {}) or {})
        genome.metadata["fitness_result"] = result.to_dict()
        genome.metadata["fitness_accepted"] = result.accepted
# ----------------------------------------------------------------------
# Functional helpers
# ----------------------------------------------------------------------
def calculate_fitness(
    genome: AlphaGenome,
    metrics: Optional[Mapping[str, Any]] = None,
    oos_metrics: Optional[Mapping[str, Any]] = None,
    config: Optional[AlphaFitnessConfig] = None,
) -> FitnessResult:
    """Evaluate one genome using a one-off evaluator."""
    return AlphaFitnessEvaluator(config).evaluate(
        genome,
        metrics=metrics,
        oos_metrics=oos_metrics,
    )
def is_alpha_accepted(
    genome: AlphaGenome,
    metrics: Optional[Mapping[str, Any]] = None,
    oos_metrics: Optional[Mapping[str, Any]] = None,
    config: Optional[AlphaFitnessConfig] = None,
) -> bool:
    """Return only the acceptance decision without mutating the genome."""
    result = AlphaFitnessEvaluator(config).acceptance_check(
        genome,
        metrics=metrics,
        oos_metrics=oos_metrics,
    )
    return result.accepted
__all__ = [
    "AlphaFitnessError",
    "MissingFitnessMetricsError",
    "InvalidFitnessMetricsError",
    "AlphaFitnessConfig",
    "FitnessResult",
    "AlphaFitnessEvaluator",
    "calculate_fitness",
    "is_alpha_accepted",
]
