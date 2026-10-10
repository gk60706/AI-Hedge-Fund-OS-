from __future__ import annotations

import copy
import random

from evolution.alpha_crossover import AlphaCrossover
from evolution.alpha_mutation import AlphaMutation


class AlphaEvolution:
    def __init__(self):
        self.crossover = AlphaCrossover()
        self.mutation = AlphaMutation()

    def evolve(self, ranked, population_size=100):
        if not ranked:
            return []
        elite_count = max(5, population_size // 10)
        elites = ranked[:elite_count]
        new_population = [
            copy.deepcopy(item["expression"])
            for item in elites
        ]
        while len(new_population) < population_size:
            parent_a = random.choice(elites)["expression"]
            parent_b = random.choice(elites)["expression"]
            child = self.crossover.crossover(
                parent_a,
                parent_b,
            )
            child = self.mutation.mutate(
                child,
                probability=0.30,
            )
            new_population.append(child)
        return new_population

# ============================================================
# V3.9.3 Alpha Evolution Engine (append)
# 旧版 AlphaEvolution 保留（tests/test_v39.py 依赖）。
# V3.9.3 新类与旧类名无冲突，追加段使用私有别名 _EVGenome
# 指向 AlphaGenomeV393，避免模块级重绑定影响旧代码。
# ============================================================

"""
AI Hedge Fund OS - V3.9.3
File: evolution/alpha_evolution.py
Orchestrates the Alpha genetic evolution loop.
Python: 3.11+
Responsibilities
----------------
- Initialize and manage the Alpha population.
- Request real training/OOS metrics from an external research evaluator.
- Calculate fitness using AlphaFitnessEvaluator.
- Rank candidates and evolve the next generation.
- Track generation reports, diversity, and stopping conditions.
- Keep OOS acceptance separate from training fitness.
- Export experiment results as JSON-compatible dictionaries.
Important
---------
This module does not calculate financial metrics from raw market data.
Supply a research_evaluator callback that performs the actual signal
evaluation, backtesting, and validation using the existing V3.9.2 pipeline.
No broker integration or live-trading interface is provided.
"""
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional
# V3.9.3 基于项目的 AlphaGenomeV393。
from evolution.alpha_genome import (
    AlphaGenomeV393 as _EVGenome,
)
from evolution.population import (
    AlphaPopulation,
    AlphaPopulationConfig,
    EvolutionError,
    InvalidPopulationError,
)
from evolution.fitness import (
    AlphaFitnessConfig,
    AlphaFitnessEvaluator,
    AlphaFitnessError,
    FitnessResult,
)
# Expected return shape from the external research evaluator:
#
# {
#     "metrics": {
#         "ic": 0.03,
#         "icir": 0.80,
#         "quantile_spread": 0.02,
#         "long_short_spread": 0.015,
#         "hit_rate": 0.53,
#         "turnover": 0.20,
#         "complexity": 5,
#     },
#     "oos_metrics": {
#         "oos_ic": 0.02,
#         "oos_icir": 0.50,
#         "oos_quantile_spread": 0.01,
#         "oos_turnover": 0.22,
#         "oos_passed": True,
#     },
# }
#
# These are examples of the schema only, not real results.
ResearchEvaluator = Callable[
    [_EVGenome],
    Mapping[str, Any],
]
class AlphaEvolutionError(RuntimeError):
    """Base exception for Alpha evolution."""
class ResearchEvaluatorError(AlphaEvolutionError):
    """Raised when the research evaluator returns invalid data."""
class EvolutionConfigurationError(AlphaEvolutionError):
    """Raised for invalid evolution configuration."""
@dataclass
class AlphaEvolutionConfig:
    """Top-level evolution run configuration."""
    max_generations: int = 20
    # Early stopping
    patience: Optional[int] = 5
    min_improvement: float = 1e-6
    target_fitness: Optional[float] = None
    # Acceptance / stopping
    stop_when_accepted: bool = False
    min_accepted_per_generation: int = 1
    # Initialization
    initialize_if_empty: bool = True
    evaluate_elites_each_generation: bool = True
    # Runtime safety
    fail_fast: bool = True
    max_consecutive_generation_errors: int = 3
    # Experiment metadata
    experiment_name: str = "alpha_evolution_v393"
    random_seed: int = 42
    def __post_init__(self) -> None:
        if self.max_generations < 1:
            raise ValueError("max_generations must be >= 1")
        if self.patience is not None and self.patience < 1:
            raise ValueError("patience must be None or >= 1")
        if (
            not math.isfinite(self.min_improvement)
            or self.min_improvement < 0
        ):
            raise ValueError("min_improvement must be finite and >= 0")
        if self.target_fitness is not None and not math.isfinite(
            self.target_fitness
        ):
            raise ValueError("target_fitness must be finite")
        if self.min_accepted_per_generation < 0:
            raise ValueError("min_accepted_per_generation must be >= 0")
        if self.max_consecutive_generation_errors < 1:
            raise ValueError(
                "max_consecutive_generation_errors must be >= 1"
            )
        if not self.experiment_name.strip():
            raise ValueError("experiment_name must not be empty")
@dataclass
class GenerationReport:
    """Metrics and status for one evaluated generation."""
    generation: int
    population_size: int
    evaluated_count: int
    accepted_count: int
    oos_passed_count: int
    best_fitness: Optional[float]
    mean_fitness: Optional[float]
    best_genome_id: Optional[str]
    best_expression: Optional[str]
    unique_expression_count: int
    expression_diversity: float
    mean_complexity: Optional[float]
    elapsed_seconds: float
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
@dataclass
class EvolutionRunResult:
    """Final result for a complete evolution run."""
    experiment_name: str
    status: str
    stop_reason: str
    initial_generation: int
    final_generation: int
    generations_completed: int
    best_genome: Optional[dict[str, Any]]
    accepted_genomes: list[dict[str, Any]]
    generation_reports: list[dict[str, Any]]
    started_at: str
    finished_at: str
    elapsed_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
class AlphaEvolutionEngine:
    """
    High-level coordinator for Alpha evolution.
    Parameters
    ----------
    population:
        An initialized or empty AlphaPopulation.
    research_evaluator:
        Callable that evaluates one genome and returns training/OOS metrics.
        It must use the existing project research/backtest/validation pipeline.
    fitness_evaluator:
        Optional AlphaFitnessEvaluator.
    config:
        Evolution run settings.
    The research_evaluator must not train on final OOS data. If it performs
    model selection, use a separate validation period and reserve the final
    OOS period for the configured acceptance check.
    """
    def __init__(
        self,
        population: Optional[AlphaPopulation] = None,
        research_evaluator: Optional[ResearchEvaluator] = None,
        fitness_evaluator: Optional[AlphaFitnessEvaluator] = None,
        config: Optional[AlphaEvolutionConfig] = None,
    ) -> None:
        self.config = config or AlphaEvolutionConfig()
        # 注意：不能使用 `population or AlphaPopulation(...)`——
        # AlphaPopulation 定义了 __len__，空种群的 bool 值为 False，
        # 会导致传入的空种群被 or 丢弃并替换为默认种群。
        self.population = (
            population
            if population is not None
            else AlphaPopulation(
                config=AlphaPopulationConfig(
                    seed=self.config.random_seed,
                )
            )
        )
        self.research_evaluator = research_evaluator
        self.fitness_evaluator = fitness_evaluator or (
            AlphaFitnessEvaluator(AlphaFitnessConfig())
        )
        self.generation_reports: list[GenerationReport] = []
        self.fitness_results: dict[str, FitnessResult] = {}
        self.run_metadata: dict[str, Any] = {}
        self._best_fitness_seen: Optional[float] = None
        self._generations_without_improvement = 0
        self._consecutive_errors = 0
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        max_generations: Optional[int] = None,
    ) -> EvolutionRunResult:
        """
        Run the evolution loop.
        Each loop iteration:
        1. Evaluates the current population using real research metrics.
        2. Calculates fitness and OOS acceptance.
        3. Records generation statistics.
        4. Checks stopping conditions.
        5. Creates the next generation when appropriate.
        max_generations is the number of generations to evaluate during this
        call, not an absolute generation number.
        """
        if self.research_evaluator is None:
            raise ResearchEvaluatorError(
                "A research_evaluator callback is required. Connect the "
                "existing Alpha metrics/backtest/validation pipeline; "
                "the evolution engine will not invent financial metrics."
            )
        generations_to_run = (
            self.config.max_generations
            if max_generations is None
            else max_generations
        )
        if generations_to_run < 1:
            raise ValueError("max_generations must be >= 1")
        if self.population.is_empty:
            if not self.config.initialize_if_empty:
                raise InvalidPopulationError(
                    "Population is empty and initialize_if_empty=False"
                )
            self.population.initialize()
        started_monotonic = time.monotonic()
        started_at = self._utc_now()
        initial_generation = self.population.generation
        stop_reason = "max_generations_reached"
        status = "completed"
        for _ in range(generations_to_run):
            generation_started = time.monotonic()
            errors: list[str] = []
            try:
                report = self.evaluate_generation(
                    elapsed_seconds=0.0,
                    errors=errors,
                )
                report.elapsed_seconds = max(
                    0.0,
                    time.monotonic() - generation_started,
                )
                self.generation_reports.append(report)
                self._consecutive_errors = 0
            except Exception as exc:
                self._consecutive_errors += 1
                message = (
                    f"Generation {self.population.generation} evaluation "
                    f"failed: {type(exc).__name__}: {exc}"
                )
                if self.config.fail_fast:
                    raise AlphaEvolutionError(message) from exc
                if self._consecutive_errors >= (
                    self.config.max_consecutive_generation_errors
                ):
                    status = "failed"
                    stop_reason = "too_many_consecutive_errors"
                    break
                # Do not create a new generation from an unevaluated
                # population after an evaluation failure.
                continue
            stop_reason = self._check_stop_conditions(report)
            if stop_reason is not None:
                break
            # Do not generate an unnecessary next generation after the final
            # requested evaluation.
            completed_this_run = len(self.generation_reports)
            if completed_this_run >= generations_to_run:
                stop_reason = "max_generations_reached"
                break
            try:
                self.population = self.population.create_next_generation()
            except (
                EvolutionError,
                InvalidPopulationError,
                ValueError,
                RuntimeError,
            ) as exc:
                message = (
                    f"Generation transition failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                if self.config.fail_fast:
                    raise AlphaEvolutionError(message) from exc
                status = "failed"
                stop_reason = "next_generation_failed"
                break
        finished_at = self._utc_now()
        elapsed = max(0.0, time.monotonic() - started_monotonic)
        best = self._best_genome()
        accepted = self._accepted_genomes()
        return EvolutionRunResult(
            experiment_name=self.config.experiment_name,
            status=status,
            stop_reason=stop_reason,
            initial_generation=initial_generation,
            final_generation=self.population.generation,
            generations_completed=len(self.generation_reports),
            best_genome=best.to_dict() if best else None,
            accepted_genomes=[g.to_dict() for g in accepted],
            generation_reports=[
                report.to_dict()
                for report in self.generation_reports
            ],
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed,
            metadata={
                "random_seed": self.config.random_seed,
                "population_config": asdict(self.population.config),
                "evolution_config": asdict(self.config),
                "fitness_config": asdict(
                    self.fitness_evaluator.config
                ),
                "research_evaluator_required": True,
                "live_trading_enabled": False,
            },
        )
    def evaluate_generation(
        self,
        elapsed_seconds: float = 0.0,
        errors: Optional[list[str]] = None,
    ) -> GenerationReport:
        """Evaluate all genomes in the current population."""
        if self.research_evaluator is None:
            raise ResearchEvaluatorError(
                "research_evaluator callback is not configured"
            )
        if self.population.is_empty:
            raise InvalidPopulationError(
                "Cannot evaluate an empty population"
            )
        errors = errors if errors is not None else []
        accepted_count = 0
        oos_passed_count = 0
        evaluated_count = 0
        for genome in self.population:
            try:
                payload = self._call_research_evaluator(genome)
                training_metrics, oos_metrics = self._parse_payload(payload)
                result = self.fitness_evaluator.evaluate(
                    genome,
                    metrics=training_metrics,
                    oos_metrics=oos_metrics,
                    apply_to_genome=True,
                )
                self.fitness_results[genome.genome_id] = result
                evaluated_count += 1
                if result.accepted:
                    accepted_count += 1
                if result.oos_passed is True:
                    oos_passed_count += 1
            except Exception as exc:
                message = (
                    f"Genome {genome.genome_id} evaluation failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                errors.append(message)
                # Failed candidates receive no fabricated score. A genome
                # that had stale metrics is reset so it cannot retain a
                # previously successful fitness after a failed evaluation.
                self._invalidate_failed_evaluation(genome)
                if self.config.fail_fast:
                    raise ResearchEvaluatorError(message) from exc
        self.population.assign_ranks()
        stats = self.population.statistics()
        best = self._best_genome_in_current_population()
        best_fitness = (
            self._finite_fitness(best) if best is not None else None
        )
        report = GenerationReport(
            generation=self.population.generation,
            population_size=len(self.population),
            evaluated_count=evaluated_count,
            accepted_count=accepted_count,
            oos_passed_count=oos_passed_count,
            best_fitness=best_fitness,
            mean_fitness=stats.mean_fitness,
            best_genome_id=best.genome_id if best else None,
            best_expression=best.expression_string if best else None,
            unique_expression_count=stats.unique_expression_count,
            expression_diversity=stats.expression_diversity,
            mean_complexity=stats.mean_complexity,
            elapsed_seconds=elapsed_seconds,
            errors=list(errors),
            metadata={
                "finite_fitness_count": stats.finite_fitness_count,
                "missing_or_failed_evaluations": len(errors),
            },
        )
        self._update_improvement_state(best_fitness)
        return report
    def step(self) -> GenerationReport:
        """
        Evaluate the current generation and create the next one.
        This is a single evolutionary step, suitable for a custom scheduler.
        The returned report describes the generation that was just evaluated.
        """
        report = self.evaluate_generation()
        stop_reason = self._check_stop_conditions(report)
        if stop_reason is None:
            self.population = self.population.create_next_generation()
        self.generation_reports.append(report)
        return report
    def evaluate_one(
        self,
        genome: _EVGenome,
    ) -> FitnessResult:
        """Run research evaluation and fitness calculation for one genome."""
        if self.research_evaluator is None:
            raise ResearchEvaluatorError(
                "research_evaluator callback is not configured"
            )
        payload = self._call_research_evaluator(genome)
        training_metrics, oos_metrics = self._parse_payload(payload)
        result = self.fitness_evaluator.evaluate(
            genome,
            metrics=training_metrics,
            oos_metrics=oos_metrics,
            apply_to_genome=True,
        )
        self.fitness_results[genome.genome_id] = result
        return result
    def get_generation_history(self) -> list[dict[str, Any]]:
        """Return recorded generation reports."""
        return [report.to_dict() for report in self.generation_reports]
    def get_accepted_genomes(self) -> list[_EVGenome]:
        """Return current-population genomes that passed fitness acceptance."""
        return self._accepted_genomes()
    def export_state(self) -> dict[str, Any]:
        """Export population and run history for JSON persistence."""
        return {
            "schema_version": "3.9.3",
            "experiment_name": self.config.experiment_name,
            "config": asdict(self.config),
            "population": self.population.to_dict(),
            "generation_reports": self.get_generation_history(),
            "fitness_results": {
                key: result.to_dict()
                for key, result in self.fitness_results.items()
            },
            "run_metadata": dict(self.run_metadata),
        }
    # ------------------------------------------------------------------
    # Research evaluator integration
    # ------------------------------------------------------------------
    def _call_research_evaluator(
        self,
        genome: _EVGenome,
    ) -> Mapping[str, Any]:
        assert self.research_evaluator is not None
        payload = self.research_evaluator(genome)
        if not isinstance(payload, Mapping):
            raise ResearchEvaluatorError(
                "research_evaluator must return a mapping/dictionary"
            )
        return payload
    @staticmethod
    def _parse_payload(
        payload: Mapping[str, Any],
    ) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
        """
        Parse a research evaluator result.
        Preferred form:
            {"metrics": {...}, "oos_metrics": {...}}
        Flat form is also accepted for training metrics only:
            {"ic": ..., "icir": ..., ...}
        OOS results must be explicitly placed in oos_metrics.
        """
        if "metrics" in payload:
            training = payload.get("metrics")
            oos = payload.get("oos_metrics")
            if not isinstance(training, Mapping):
                raise ResearchEvaluatorError(
                    "'metrics' must contain a mapping"
                )
            if oos is not None and not isinstance(oos, Mapping):
                raise ResearchEvaluatorError(
                    "'oos_metrics' must contain a mapping or None"
                )
            return dict(training), dict(oos) if oos is not None else None
        reserved = {
            "oos_metrics",
            "metadata",
            "experiment_id",
            "data_version",
        }
        training = {
            key: value
            for key, value in payload.items()
            if key not in reserved
        }
        oos = payload.get("oos_metrics")
        if oos is not None and not isinstance(oos, Mapping):
            raise ResearchEvaluatorError(
                "'oos_metrics' must contain a mapping or None"
            )
        return training, dict(oos) if oos is not None else None
    # ------------------------------------------------------------------
    # Stopping and improvement tracking
    # ------------------------------------------------------------------
    def _update_improvement_state(
        self,
        current_fitness: Optional[float],
    ) -> None:
        if current_fitness is None or not math.isfinite(current_fitness):
            self._generations_without_improvement += 1
            return
        if self._best_fitness_seen is None:
            self._best_fitness_seen = current_fitness
            self._generations_without_improvement = 0
            return
        if current_fitness > (
            self._best_fitness_seen + self.config.min_improvement
        ):
            self._best_fitness_seen = current_fitness
            self._generations_without_improvement = 0
        else:
            self._generations_without_improvement += 1
    def _check_stop_conditions(
        self,
        report: GenerationReport,
    ) -> Optional[str]:
        if (
            self.config.target_fitness is not None
            and report.best_fitness is not None
            and report.best_fitness >= self.config.target_fitness
        ):
            return "target_fitness_reached"
        if (
            self.config.stop_when_accepted
            and report.accepted_count
            >= self.config.min_accepted_per_generation
        ):
            return "accepted_alpha_found"
        if (
            self.config.patience is not None
            and self._generations_without_improvement
            >= self.config.patience
        ):
            return "fitness_plateau_patience_reached"
        return None
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _finite_fitness(
        genome: Optional[_EVGenome],
    ) -> Optional[float]:
        if genome is None:
            return None
        try:
            value = float(genome.fitness)
        except (TypeError, ValueError, OverflowError):
            return None
        return value if math.isfinite(value) else None
    def _best_genome_in_current_population(
        self,
    ) -> Optional[_EVGenome]:
        finite = [
            genome
            for genome in self.population
            if self._finite_fitness(genome) is not None
        ]
        if not finite:
            return None
        return max(
            finite,
            key=lambda genome: float(genome.fitness),
        )
    def _best_genome(self) -> Optional[_EVGenome]:
        return self._best_genome_in_current_population()
    def _accepted_genomes(self) -> list[_EVGenome]:
        accepted: list[_EVGenome] = []
        for genome in self.population:
            result = self.fitness_results.get(genome.genome_id)
            if result is not None and result.accepted:
                accepted.append(genome)
        accepted.sort(
            key=lambda genome: (
                self._finite_fitness(genome)
                if self._finite_fitness(genome) is not None
                else float("-inf")
            ),
            reverse=True,
        )
        return accepted
    @staticmethod
    def _invalidate_failed_evaluation(genome: _EVGenome) -> None:
        """Prevent stale successful scores surviving a failed re-evaluation."""
        genome.fitness = float("-inf")
        genome.rank = None
        genome.selected = False
        genome.elite = False
        # Remove the cached result so failed candidates cannot remain marked
        # as accepted in the current run.
        genome.metadata = dict(getattr(genome, "metadata", {}) or {})
        genome.metadata.pop("fitness_result", None)
        genome.metadata["fitness_evaluation_error"] = True
    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
# ----------------------------------------------------------------------
# Functional helpers
# ----------------------------------------------------------------------
def run_alpha_evolution(
    population: AlphaPopulation,
    research_evaluator: ResearchEvaluator,
    config: Optional[AlphaEvolutionConfig] = None,
    fitness_config: Optional[AlphaFitnessConfig] = None,
) -> EvolutionRunResult:
    """Convenience function to run an Alpha evolution experiment."""
    engine = AlphaEvolutionEngine(
        population=population,
        research_evaluator=research_evaluator,
        fitness_evaluator=AlphaFitnessEvaluator(fitness_config),
        config=config,
    )
    return engine.run()
__all__ = [
    "ResearchEvaluator",
    "AlphaEvolutionError",
    "ResearchEvaluatorError",
    "EvolutionConfigurationError",
    "AlphaEvolutionConfig",
    "GenerationReport",
    "EvolutionRunResult",
    "AlphaEvolutionEngine",
    "run_alpha_evolution",
]
