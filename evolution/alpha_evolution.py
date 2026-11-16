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
import json
import math
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
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
from evolution.evolution_history import (
    EvolutionHistory,
    EvolutionHistoryConfig,
)
from evolution.file_lock import FileLock
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
class CheckpointError(AlphaEvolutionError):
    """Base exception for checkpoint operations."""
class CheckpointVersionError(CheckpointError):
    """Raised when a checkpoint uses an unsupported schema version."""
class CheckpointCorruptionError(CheckpointError):
    """Raised when checkpoint data is missing, malformed or invalid."""
class CheckpointConsistencyError(CheckpointError):
    """Raised when checkpoint state conflicts with persisted history."""
def _rng_state_to_json(value: Any) -> Any:
    """Convert random.Random state tuples into JSON-compatible lists."""
    if isinstance(value, tuple):
        return [_rng_state_to_json(item) for item in value]
    if isinstance(value, list):
        return [_rng_state_to_json(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(
        f"Unsupported random state value: {type(value).__name__}"
    )
def _rng_state_from_json(value: Any) -> Any:
    """Rebuild the nested tuple structure required by random.setstate()."""
    if isinstance(value, list):
        return tuple(_rng_state_from_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(
        f"Invalid random state value: {type(value).__name__}"
    )
def _json_safe_numbers(value: Any) -> Any:
    """Recursively convert NaN/Infinity to None.

    未评估的基因以 NaN / -inf 存储（这是内部“无量”标记）。
    JSON 标准不允许这两个字面量，写盘前必须显式转换；
    恢复时 AlphaGenome.from_dict 会把 None 还原为同一默认值。
    """
    if isinstance(value, dict):
        return {
            str(key): _json_safe_numbers(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe_numbers(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
def _population_component_rngs(population: AlphaPopulation) -> dict[str, Any]:
    """Collect all RNG objects that affect offspring generation.

    仅保存 population._rng 不够：交叉/变异/新个体生成器各自持有独立
    Random 实例，恢复时必须连它们的序列位置一起恢复，否则续跑会在
    第一代就抽出不同的父代与算子，产生不可复现的分支。
    """
    candidates: dict[str, Any] = {
        "population": getattr(population, "_rng", None),
        "mutation_engine": getattr(
            getattr(population, "mutation_engine", None), "rng", None
        ),
        "crossover_engine": getattr(
            getattr(population, "crossover_engine", None), "rng", None
        ),
        "generator": getattr(
            getattr(population, "generator", None), "random", None
        ),
    }
    return {
        name: rng
        for name, rng in candidates.items()
        if rng is not None and hasattr(rng, "getstate")
    }
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
        history: Optional[EvolutionHistory] = None,
    ) -> None:
        self.config = config or AlphaEvolutionConfig()
        self.history = history or EvolutionHistory(
            config=EvolutionHistoryConfig(
                output_path="experiments/runs/evolution_history.jsonl",
                enabled=True,
                flush_each_record=True,
            ),
            metadata={
                "experiment_name": self.config.experiment_name,
                "random_seed": self.config.random_seed,
                "engine": "AlphaEvolutionEngine",
                "version": "3.9.3",
                "live_trading_enabled": False,
            },
        )
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
        # 最近一次成功完成评估的种群代数；用于连续 run() 调用时
        # 避免重复评估上一轮已经研究过的同一代 Alpha。
        self._last_evaluated_generation: Optional[int] = None
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        max_generations: Optional[int] = None,
    ) -> EvolutionRunResult:
        """
        Run the evolution loop.
        max_generations 表示本次调用要评估的代数，而不是绝对代数。
        本次返回结果只统计本次运行，不混入之前调用的报告。
        """
        started_monotonic = time.monotonic()
        started_at = self._utc_now()
        report_start_index = len(self.generation_reports)
        initial_generation = self.population.generation
        generations_to_run = (
            self.config.max_generations
            if max_generations is None
            else max_generations
        )
        stop_reason = "max_generations_reached"
        status = "completed"
        try:
            if self.research_evaluator is None:
                raise ResearchEvaluatorError(
                    "A research_evaluator callback is required. Connect the "
                    "existing Alpha metrics/backtest/validation pipeline; "
                    "the evolution engine will not invent financial metrics."
                )
            if generations_to_run < 1:
                raise ValueError("max_generations must be >= 1")
            reinitialized = False
            if self.population.is_empty:
                if not self.config.initialize_if_empty:
                    raise InvalidPopulationError(
                        "Population is empty and initialize_if_empty=False"
                    )
                self.population.initialize()
                reinitialized = True
            # 连续运行规则：若当前种群在上一轮 run() 中已被评估过，
            # 且本次没有重新初始化，就先生成下一代再评估，避免重复
            # 研究同一批 Alpha 并让历史记录出现重复代数编号。
            if (
                not reinitialized
                and self._last_evaluated_generation is not None
                and self.population.generation
                == self._last_evaluated_generation
            ):
                # 生成下一代失败时直接落入外层统一失败收尾：
                # 运行标记为失败、异常写入历史后再抛出。
                self.population = self.population.create_next_generation()
            initial_generation = self.population.generation
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
                    # 只有成功完成评估才更新最近已评估代数；
                    # 评估失败不消耗当前代，下一次 run() 仍从该代开始。
                    self._last_evaluated_generation = report.generation
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
                    # 评估失败时不基于未评估种群生成下一代。
                    continue
                stop_reason_from_report = self._check_stop_conditions(report)
                if stop_reason_from_report is not None:
                    stop_reason = stop_reason_from_report
                    break
                # 关键修复：只统计本次 run() 新产生的报告。
                completed_this_run = (
                    len(self.generation_reports) - report_start_index
                )
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
                        "Generation transition failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    if self.config.fail_fast:
                        raise AlphaEvolutionError(message) from exc
                    status = "failed"
                    stop_reason = "next_generation_failed"
                    break
        except Exception as exc:
            # 统一失败收尾：尽可能将失败状态写入历史，再向调用方抛出异常。
            if isinstance(exc, AlphaEvolutionError):
                recorded_error = exc
            else:
                recorded_error = AlphaEvolutionError(
                    f"Evolution run failed: {type(exc).__name__}: {exc}"
                )
            try:
                self.history.finish(
                    status="failed",
                    stop_reason=stop_reason or "exception",
                    error=recorded_error,
                    metadata={
                        "experiment_name": self.config.experiment_name,
                        "generations_completed": (
                            len(self.generation_reports) - report_start_index
                        ),
                        "initial_generation": initial_generation,
                        "final_generation": self.population.generation,
                        "live_trading_enabled": False,
                    },
                )
            except Exception as history_exc:
                # 保留原始运行异常，不让历史写入错误将其覆盖。
                if hasattr(recorded_error, "add_note"):
                    recorded_error.add_note(
                        "Additionally, finalizing evolution history failed: "
                        f"{type(history_exc).__name__}: {history_exc}"
                    )
            if recorded_error is exc:
                raise
            raise recorded_error from exc
        finished_at = self._utc_now()
        elapsed = max(0.0, time.monotonic() - started_monotonic)
        # 返回值仅使用本次 run() 新产生的报告。
        run_reports = self.generation_reports[report_start_index:]
        best = self._best_genome()
        accepted = self._accepted_genomes()
        result = EvolutionRunResult(
            experiment_name=self.config.experiment_name,
            status=status,
            stop_reason=stop_reason,
            initial_generation=initial_generation,
            final_generation=self.population.generation,
            generations_completed=len(run_reports),
            best_genome=best.to_dict() if best else None,
            accepted_genomes=[g.to_dict() for g in accepted],
            generation_reports=[
                report.to_dict() for report in run_reports
            ],
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed,
            metadata={
                "random_seed": self.config.random_seed,
                "population_config": asdict(self.population.config),
                "evolution_config": asdict(self.config),
                "fitness_config": asdict(self.fitness_evaluator.config),
                "research_evaluator_required": True,
                "live_trading_enabled": False,
                "history_run_id": self.history.run_id,
                "report_start_index": report_start_index,
            },
        )
        final_history_status = (
            "failed"
            if status == "failed"
            else "stopped"
            if stop_reason != "max_generations_reached"
            else "completed"
        )
        self.history.finish(
            status=final_history_status,
            stop_reason=stop_reason,
            metadata={
                "experiment_name": self.config.experiment_name,
                "generations_completed": result.generations_completed,
                "initial_generation": result.initial_generation,
                "final_generation": result.final_generation,
                "live_trading_enabled": False,
            },
        )
        return result
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
        # Persist generation-level research and fitness history.
        try:
            self.history.record_generation(
                generation=report.generation,
                population=list(self.population),
                report=report,
                best_genome=best,
                metrics={
                    "best_fitness": report.best_fitness,
                    "mean_fitness": report.mean_fitness,
                    "accepted_count": report.accepted_count,
                    "oos_passed_count": report.oos_passed_count,
                    "evaluated_count": report.evaluated_count,
                    "unique_expression_count": (
                        report.unique_expression_count
                    ),
                    "expression_diversity": (
                        report.expression_diversity
                    ),
                    "mean_complexity": report.mean_complexity,
                },
                metadata={
                    "experiment_name": self.config.experiment_name,
                    "random_seed": self.config.random_seed,
                    "evaluation_errors": report.errors,
                },
            )
        except Exception as exc:
            # History persistence errors must not silently corrupt
            # the research metrics or the genome fitness values.
            if self.config.fail_fast:
                raise AlphaEvolutionError(
                    "Failed to persist evolution generation history: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
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
    def get_evolution_history_summary(self) -> dict[str, Any]:
        """Return a compact summary of the current evolution history."""
        return self.history.summary()
    def get_persisted_evolution_history(
        self,
        record_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Load persisted history records for this run."""
        return self.history.load_persisted_records(
            record_type=record_type,
        )
    def get_accepted_genomes(self) -> list[_EVGenome]:
        """Return current-population genomes that passed fitness acceptance."""
        return self._accepted_genomes()
    def export_state(self) -> dict[str, Any]:
        """Export a complete, JSON-compatible evolution checkpoint."""
        history_config = asdict(self.history.config)

        state = {
            "schema_version": "3.9.3",
            "experiment_name": self.config.experiment_name,
            "created_at": self._utc_now(),
            "config": asdict(self.config),
            "population": self.population.to_dict(),
            "rng_state": _rng_state_to_json(
                self.population._rng.getstate()
            ),
            "component_rng_states": {
                name: _rng_state_to_json(rng.getstate())
                for name, rng in _population_component_rngs(
                    self.population
                ).items()
            },
            "generation_reports": self.get_generation_history(),
            "fitness_results": {
                key: result.to_dict()
                for key, result in self.fitness_results.items()
            },
            "run_metadata": dict(self.run_metadata),
            "last_evaluated_generation": (
                self._last_evaluated_generation
            ),
            "_best_fitness_seen": self._best_fitness_seen,
            "_generations_without_improvement": (
                self._generations_without_improvement
            ),
            "_consecutive_errors": self._consecutive_errors,
            "history_run_id": self.history.run_id,
            "history_config": history_config,
        }
        return _json_safe_numbers(state)

    # ------------------------------------------------------------------
    # Checkpoint: save / restore / resume
    # ------------------------------------------------------------------
    def save_checkpoint(self, path: str | Path) -> Path:
        """Atomically write the current engine state to a JSON checkpoint."""
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            state = self.export_state()

            # Validate JSON serializability before creating/replacing the file.
            serialized = json.dumps(
                state,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
            )

            # 同一路径的并发写必须串行，否则“最后一次原子替换”虽不损坏
            # 文件，但写入顺序不可控，恢复时可能拿到较旧的状态。
            with FileLock(target, timeout=30.0):
                fd, temporary_name = tempfile.mkstemp(
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    dir=str(target.parent),
                    text=True,
                )
                temporary_path = Path(temporary_name)

                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(serialized)
                        handle.write("\n")
                        handle.flush()
                        os.fsync(handle.fileno())

                    os.replace(temporary_path, target)
                except Exception:
                    try:
                        temporary_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise

            return target
        except CheckpointError:
            raise
        except Exception as exc:
            raise CheckpointError(
                f"Could not save checkpoint to {target}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore engine state. Existing state is not changed on validation failure."""
        required = {
            "schema_version",
            "experiment_name",
            "config",
            "population",
            "rng_state",
            "generation_reports",
            "fitness_results",
            "run_metadata",
            "last_evaluated_generation",
            "_best_fitness_seen",
            "_generations_without_improvement",
            "_consecutive_errors",
            "created_at",
        }

        if not isinstance(state, dict):
            raise CheckpointCorruptionError(
                "Checkpoint root must be a dictionary"
            )

        missing = sorted(required - set(state))
        if missing:
            raise CheckpointCorruptionError(
                f"Checkpoint is missing required fields: {missing}"
            )

        if state["schema_version"] != "3.9.3":
            raise CheckpointVersionError(
                "Unsupported checkpoint schema_version: "
                f"{state['schema_version']!r}; expected '3.9.3'"
            )

        if state["experiment_name"] != self.config.experiment_name:
            raise CheckpointConsistencyError(
                "Checkpoint experiment_name does not match engine config: "
                f"{state['experiment_name']!r} != "
                f"{self.config.experiment_name!r}"
            )

        try:
            raw_config = state["config"]
            if not isinstance(raw_config, dict):
                raise ValueError("'config' must be a dictionary")

            checkpoint_config = AlphaEvolutionConfig(**raw_config)
            if (
                checkpoint_config.experiment_name
                != self.config.experiment_name
            ):
                raise ValueError(
                    "config.experiment_name conflicts with experiment_name"
                )

            raw_population = state["population"]
            if not isinstance(raw_population, dict):
                raise ValueError("'population' must be a dictionary")

            restored_population = AlphaPopulation.from_dict(raw_population)

            # AlphaPopulation.from_dict() resets RNG from config.seed.
            # Restore the exact saved random state after population reconstruction.
            restored_rng_state = _rng_state_from_json(state["rng_state"])
            restored_population._rng.setstate(restored_rng_state)

            # 交叉/变异/生成器各有独立 RNG，必须一并恢复，否则续跑不可复现。
            raw_component_states = state.get("component_rng_states")
            if raw_component_states is not None:
                if not isinstance(raw_component_states, dict):
                    raise ValueError(
                        "'component_rng_states' must be a dictionary"
                    )
                component_rngs = _population_component_rngs(
                    restored_population
                )
                for name, raw_state in raw_component_states.items():
                    rng = component_rngs.get(name)
                    if rng is None:
                        raise ValueError(
                            f"Checkpoint has RNG state for unknown component {name!r}"
                        )
                    rng.setstate(_rng_state_from_json(raw_state))

            raw_reports = state["generation_reports"]
            if not isinstance(raw_reports, list):
                raise ValueError("'generation_reports' must be a list")

            report_fields = set(GenerationReport.__dataclass_fields__)
            restored_reports: list[GenerationReport] = []
            for index, item in enumerate(raw_reports):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"generation_reports[{index}] must be a dictionary"
                    )
                unknown = set(item) - report_fields
                if unknown:
                    raise ValueError(
                        f"generation_reports[{index}] has unknown fields: "
                        f"{sorted(unknown)}"
                    )
                restored_reports.append(GenerationReport(**item))

            raw_fitness = state["fitness_results"]
            if not isinstance(raw_fitness, dict):
                raise ValueError("'fitness_results' must be a dictionary")

            restored_fitness: dict[str, FitnessResult] = {}
            for genome_id, item in raw_fitness.items():
                if not isinstance(genome_id, str) or not isinstance(item, dict):
                    raise ValueError(
                        "fitness_results must map string IDs to dictionaries"
                    )
                result = FitnessResult.from_dict(item)
                if result.genome_id != genome_id:
                    raise ValueError(
                        f"fitness_results key {genome_id!r} does not match "
                        f"result.genome_id {result.genome_id!r}"
                    )
                restored_fitness[genome_id] = result

            raw_metadata = state["run_metadata"]
            if not isinstance(raw_metadata, dict):
                raise ValueError("'run_metadata' must be a dictionary")

            last_generation = state["last_evaluated_generation"]
            if (
                last_generation is not None
                and (
                    isinstance(last_generation, bool)
                    or not isinstance(last_generation, int)
                    or last_generation < 0
                )
            ):
                raise ValueError(
                    "'last_evaluated_generation' must be None or >= 0"
                )

            best_fitness = state["_best_fitness_seen"]
            if best_fitness is not None:
                if (
                    isinstance(best_fitness, bool)
                    or not isinstance(best_fitness, (int, float))
                ):
                    raise ValueError(
                        "'_best_fitness_seen' must be numeric or None"
                    )
                if not math.isfinite(float(best_fitness)):
                    raise ValueError("'_best_fitness_seen' must be finite")

            stagnant = state["_generations_without_improvement"]
            errors = state["_consecutive_errors"]
            for name, value in (
                ("_generations_without_improvement", stagnant),
                ("_consecutive_errors", errors),
            ):
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 0
                ):
                    raise ValueError(f"{name} must be an integer >= 0")

            created_at = state["created_at"]
            if not isinstance(created_at, str) or not created_at:
                raise ValueError("'created_at' must be a non-empty string")

        except CheckpointError:
            raise
        except Exception as exc:
            raise CheckpointCorruptionError(
                f"Invalid checkpoint state: {type(exc).__name__}: {exc}"
            ) from exc

        # Commit only after every component has been reconstructed and validated.
        self.population = restored_population
        self.generation_reports = restored_reports
        self.fitness_results = restored_fitness
        self.run_metadata = dict(raw_metadata)
        self._last_evaluated_generation = last_generation
        self._best_fitness_seen = (
            None if best_fitness is None else float(best_fitness)
        )
        self._generations_without_improvement = stagnant
        self._consecutive_errors = errors

    @classmethod
    def from_checkpoint(
        cls,
        path: str | Path,
        *,
        research_evaluator: Optional[ResearchEvaluator] = None,
        fitness_evaluator: Optional[AlphaFitnessEvaluator] = None,
        history: Optional[EvolutionHistory] = None,
        strict: bool = True,
    ) -> "AlphaEvolutionEngine":
        """Create an engine from a checkpoint and verify persisted history."""
        checkpoint_path = Path(path)

        try:
            with checkpoint_path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except Exception as exc:
            raise CheckpointCorruptionError(
                f"Could not read checkpoint {checkpoint_path}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        if not isinstance(state, dict):
            raise CheckpointCorruptionError(
                "Checkpoint root must be a JSON object"
            )

        if state.get("schema_version") != "3.9.3":
            raise CheckpointVersionError(
                "Unsupported checkpoint schema_version: "
                f"{state.get('schema_version')!r}; expected '3.9.3'"
            )

        try:
            raw_config = state["config"]
            if not isinstance(raw_config, dict):
                raise ValueError("'config' must be a dictionary")
            config = AlphaEvolutionConfig(**raw_config)

            if state.get("experiment_name") != config.experiment_name:
                raise ValueError(
                    "experiment_name conflicts with config.experiment_name"
                )

            if history is None:
                raw_history_config = state.get("history_config")
                if not isinstance(raw_history_config, dict):
                    raise ValueError(
                        "history_config is required when history is not supplied"
                    )
                history_config = EvolutionHistoryConfig(**raw_history_config)
                history_run_id = state.get("history_run_id")
                if not isinstance(history_run_id, str) or not history_run_id:
                    raise ValueError(
                        "history_run_id is required when history is not supplied"
                    )
                history = EvolutionHistory(
                    config=history_config,
                    run_id=history_run_id,
                    metadata={
                        "experiment_name": config.experiment_name,
                        "engine": "AlphaEvolutionEngine",
                        "version": "3.9.3",
                        "restored_from_checkpoint": str(checkpoint_path),
                        "live_trading_enabled": False,
                    },
                )

            engine = cls(
                population=None,
                research_evaluator=research_evaluator,
                fitness_evaluator=fitness_evaluator,
                config=config,
                history=history,
            )
            engine.restore_state(state)

        except CheckpointError:
            raise
        except Exception as exc:
            raise CheckpointCorruptionError(
                f"Invalid checkpoint configuration: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        # Compare the last persisted generation for this run with the checkpoint.
        try:
            records = engine.history.load_persisted_records(
                record_type="generation",
                strict=True,
            )
            if records:
                payload = records[-1].get("payload")
                if not isinstance(payload, dict):
                    raise ValueError(
                        "Latest history generation record has no valid payload"
                    )
                history_generation = payload.get("generation")
                checkpoint_generation = engine.population.generation

                if history_generation != checkpoint_generation:
                    message = (
                        "Checkpoint/history generation mismatch: "
                        f"checkpoint={checkpoint_generation}, "
                        f"history={history_generation}, "
                        f"run_id={engine.history.run_id}"
                    )
                    if strict:
                        raise CheckpointConsistencyError(message)
                    engine.run_metadata["checkpoint_history_mismatch"] = {
                        "checkpoint_generation": checkpoint_generation,
                        "history_generation": history_generation,
                        "message": message,
                    }
            else:
                engine.run_metadata["checkpoint_history_records_missing"] = True

        except CheckpointConsistencyError:
            raise
        except Exception as exc:
            if strict:
                raise CheckpointConsistencyError(
                    "Could not verify checkpoint against JSONL history: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            engine.run_metadata["checkpoint_history_check_error"] = (
                f"{type(exc).__name__}: {exc}"
            )

        return engine

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
