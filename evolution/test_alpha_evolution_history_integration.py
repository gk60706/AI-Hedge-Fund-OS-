"""
AI Hedge Fund OS - V3.9.3
File: evolution/test_alpha_evolution_history_integration.py
Integration tests for AlphaEvolutionEngine and EvolutionHistory.
Python: 3.11+
No network access, external API keys, broker connections, or live trading.
"""
from __future__ import annotations
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional
import pytest
from evolution.alpha_evolution import (
    AlphaEvolutionConfig,
    AlphaEvolutionEngine,
    AlphaEvolutionError,
    ResearchEvaluatorError,
)
from evolution.evolution_history import (
    EvolutionHistory,
    EvolutionHistoryConfig,
)
# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
@dataclass
class FakeGenome:
    genome_id: str
    expression_string: str
    fitness: float = float("-inf")
    generation: int = 0
    ic: float = float("nan")
    icir: float = float("nan")
    quantile_spread: float = float("nan")
    turnover: float = float("nan")
    sharpe: float = float("nan")
    max_drawdown: float = float("nan")
    oos_ic: float = float("nan")
    oos_icir: float = float("nan")
    oos_sharpe: float = float("nan")
    oos_max_drawdown: float = float("nan")
    complexity: float = 1.0
    node_count: int = 1
    depth: int = 1
    rank: Optional[int] = None
    selected: bool = False
    elite: bool = False
    metadata: Optional[dict[str, Any]] = None
    @property
    def expression(self) -> str:
        return self.expression_string
    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["expression"] = self.expression_string
        result["expression_string"] = self.expression_string
        result["metadata"] = dict(self.metadata or {})
        return result
@dataclass
class FakePopulationConfig:
    population_size: int = 4
    elite_size: int = 1
    max_depth: int = 4
    max_nodes: int = 15
    seed: int = 42
@dataclass
class FakePopulationStatistics:
    mean_fitness: Optional[float]
    unique_expression_count: int
    expression_diversity: float
    mean_complexity: Optional[float]
    finite_fitness_count: int
class FakePopulation:
    """Small deterministic population implementing the engine's interface."""
    def __init__(
        self,
        genomes: Optional[list[FakeGenome]] = None,
        *,
        generation: int = 0,
        config: Optional[FakePopulationConfig] = None,
    ) -> None:
        self.genomes = list(genomes or [])
        self.generation = generation
        self.config = config or FakePopulationConfig()
    def __iter__(self):
        return iter(self.genomes)
    def __len__(self) -> int:
        return len(self.genomes)
    @property
    def is_empty(self) -> bool:
        return not self.genomes
    def initialize(self):
        if not self.genomes:
            self.genomes = [
                FakeGenome(
                    genome_id=f"alpha-{i}",
                    expression_string=f"rank(feature_{i})",
                    generation=self.generation,
                )
                for i in range(self.config.population_size)
            ]
        return self
    def assign_ranks(self) -> None:
        ranked = sorted(
            self.genomes,
            key=lambda item: (
                item.fitness
                if math.isfinite(item.fitness)
                else float("-inf")
            ),
            reverse=True,
        )
        for rank, genome in enumerate(ranked, start=1):
            genome.rank = rank
    def statistics(self) -> FakePopulationStatistics:
        finite = [
            genome.fitness
            for genome in self.genomes
            if math.isfinite(genome.fitness)
        ]
        expressions = {
            genome.expression_string for genome in self.genomes
        }
        complexities = [
            genome.complexity
            for genome in self.genomes
            if math.isfinite(genome.complexity)
        ]
        return FakePopulationStatistics(
            mean_fitness=(
                sum(finite) / len(finite) if finite else None
            ),
            unique_expression_count=len(expressions),
            expression_diversity=(
                len(expressions) / len(self.genomes)
                if self.genomes
                else 0.0
            ),
            mean_complexity=(
                sum(complexities) / len(complexities)
                if complexities
                else None
            ),
            finite_fitness_count=len(finite),
        )
    def create_next_generation(self):
        next_generation = self.generation + 1
        children = [
            FakeGenome(
                genome_id=f"g{next_generation}-alpha-{i}",
                expression_string=genome.expression_string,
                generation=next_generation,
                complexity=genome.complexity,
                node_count=genome.node_count,
                depth=genome.depth,
            )
            for i, genome in enumerate(self.genomes)
        ]
        return FakePopulation(
            children,
            generation=next_generation,
            config=self.config,
        )
    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "config": asdict(self.config),
            "genomes": [genome.to_dict() for genome in self.genomes],
        }
@dataclass
class FakeFitnessResult:
    fitness: float
    accepted: bool
    oos_passed: Optional[bool]
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
@dataclass
class FakeFitnessConfig:
    test_mode: bool = True
class FakeFitnessEvaluator:
    """Deterministic evaluator for testing engine-history integration."""
    def __init__(self) -> None:
        self.config = FakeFitnessConfig()
        self.calls = 0
    def evaluate(
        self,
        genome: FakeGenome,
        *,
        metrics: Optional[Mapping[str, Any]] = None,
        oos_metrics: Optional[Mapping[str, Any]] = None,
        apply_to_genome: bool = True,
    ) -> FakeFitnessResult:
        self.calls += 1
        metrics = dict(metrics or {})
        oos_metrics = dict(oos_metrics or {})
        score = float(metrics.get("score", 0.5))
        ic = float(metrics.get("ic", 0.03))
        icir = float(metrics.get("icir", 0.5))
        turnover = float(metrics.get("turnover", 0.2))
        complexity = float(metrics.get("complexity", 1.0))
        oos_ic = oos_metrics.get("oos_ic")
        oos_passed = oos_metrics.get("oos_passed")
        if apply_to_genome:
            genome.fitness = score
            genome.ic = ic
            genome.icir = icir
            genome.turnover = turnover
            genome.complexity = complexity
            if oos_ic is not None:
                genome.oos_ic = float(oos_ic)
            if oos_passed is not None:
                genome.metadata = dict(genome.metadata or {})
                genome.metadata["oos_passed"] = bool(oos_passed)
        return FakeFitnessResult(
            fitness=score,
            accepted=bool(oos_passed is True and oos_ic is not None),
            oos_passed=(
                bool(oos_passed)
                if oos_passed is not None
                else None
            ),
        )
# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def history_path(tmp_path: Path) -> Path:
    return tmp_path / "evolution_history.jsonl"
def make_history(
    path: Path,
    *,
    run_id: Optional[str] = None,
    enabled: bool = True,
) -> EvolutionHistory:
    return EvolutionHistory(
        config=EvolutionHistoryConfig(
            output_path=str(path),
            enabled=enabled,
            flush_each_record=True,
            strict_loading=True,
        ),
        run_id=run_id,
        metadata={"test_suite": "alpha_evolution_integration"},
    )
def make_population(size: int = 4) -> FakePopulation:
    return FakePopulation(
        [
            FakeGenome(
                genome_id=f"alpha-{i}",
                expression_string=f"rank(feature_{i})",
                complexity=float(i + 1),
            )
            for i in range(size)
        ],
        config=FakePopulationConfig(
            population_size=size,
            elite_size=1,
            seed=42,
        ),
    )
def make_research_evaluator():
    """Return deterministic training/OOS results for each genome."""
    def evaluate(genome: FakeGenome) -> Mapping[str, Any]:
        index = int(genome.genome_id.rsplit("-", 1)[-1])
        score = 0.4 + index * 0.1
        return {
            "metrics": {
                "score": score,
                "ic": 0.02 + index * 0.005,
                "icir": 0.4 + index * 0.1,
                "turnover": 0.15,
                "complexity": float(index + 1),
            },
            "oos_metrics": {
                "oos_ic": 0.015 + index * 0.002,
                "oos_passed": index >= 1,
            },
            "metadata": {"source": "integration_test"},
        }
    return evaluate
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records
def make_engine(
    history: EvolutionHistory,
    *,
    population: Optional[FakePopulation] = None,
    research_evaluator=None,
    max_generations: int = 2,
    fail_fast: bool = True,
) -> AlphaEvolutionEngine:
    return AlphaEvolutionEngine(
        population=population or make_population(),
        research_evaluator=(
            research_evaluator
            if research_evaluator is not None
            else make_research_evaluator()
        ),
        fitness_evaluator=FakeFitnessEvaluator(),
        config=AlphaEvolutionConfig(
            max_generations=max_generations,
            patience=None,
            fail_fast=fail_fast,
            experiment_name="alpha_history_integration_test",
            random_seed=42,
        ),
        history=history,
    )
# ---------------------------------------------------------------------------
# Successful run integration
# ---------------------------------------------------------------------------
def test_engine_records_one_history_snapshot_per_generation(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=3)
    result = engine.run()
    generation_records = history.load_persisted_records(
        record_type="generation"
    )
    assert result.status == "completed"
    assert result.generations_completed == 3
    assert len(generation_records) == 3
    generations = [
        record["payload"]["generation"]
        for record in generation_records
    ]
    assert generations == [0, 1, 2]
def test_generation_records_contain_metrics_and_population_statistics(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=1)
    engine.run()
    records = history.load_persisted_records(
        record_type="generation"
    )
    assert len(records) == 1
    payload = records[0]["payload"]
    assert payload["population_size"] == 4
    assert payload["evaluated_count"] == 4
    assert payload["best_fitness"] is not None
    assert payload["mean_fitness"] is not None
    assert payload["best_genome_id"] is not None
    assert payload["best_expression"] is not None
    assert payload["metrics"]["evaluated_count"] == 4
    assert payload["metrics"]["oos_passed_count"] >= 1
def test_engine_writes_run_started_and_run_finished_records(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=1)
    result = engine.run()
    records = read_jsonl(history_path)
    summaries = [
        record for record in records
        if record.get("record_type") == "run_summary"
    ]
    assert len(summaries) == 2
    assert summaries[0]["event"] == "run_started"
    assert summaries[-1]["event"] == "run_finished"
    assert summaries[-1]["payload"]["status"] == "completed"
    assert summaries[-1]["payload"]["stop_reason"] == (
        "max_generations_reached"
    )
    assert result.metadata["history_run_id"] == history.run_id
def test_result_and_history_summary_agree_on_generation_count(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=2)
    result = engine.run()
    summary = engine.get_evolution_history_summary()
    assert summary["generations_recorded"] == result.generations_completed
    assert summary["best_fitness"] == pytest.approx(
        result.best_genome["fitness"]
    )
def test_engine_can_load_persisted_generation_history(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=2)
    engine.run()
    records = engine.get_persisted_evolution_history(
        record_type="generation"
    )
    assert len(records) == 2
    assert all(record["run_id"] == history.run_id for record in records)
# ---------------------------------------------------------------------------
# Experiment isolation
# ---------------------------------------------------------------------------
def test_separate_runs_sharing_one_file_remain_isolated(
    history_path: Path,
) -> None:
    first_history = make_history(history_path, run_id="integration-run-a")
    second_history = make_history(history_path, run_id="integration-run-b")
    first_engine = make_engine(first_history, max_generations=1)
    second_engine = make_engine(
        second_history,
        population=make_population(),
        max_generations=2,
    )
    first_engine.run()
    second_engine.run()
    first_records = first_history.load_persisted_records(
        record_type="generation"
    )
    second_records = second_history.load_persisted_records(
        record_type="generation"
    )
    assert len(first_records) == 1
    assert len(second_records) == 2
    assert {record["run_id"] for record in first_records} == {
        "integration-run-a"
    }
    assert {record["run_id"] for record in second_records} == {
        "integration-run-b"
    }
def test_every_jsonl_line_is_valid_strict_json(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=2)
    engine.run()
    for line in history_path.read_text(encoding="utf-8").splitlines():
        parsed = json.loads(
            line,
            parse_constant=lambda value: (
                _reject_json_constant(value)
            ),
        )
        assert isinstance(parsed, dict)
        assert parsed["run_id"] == history.run_id
def _reject_json_constant(value: str) -> None:
    raise AssertionError(f"Non-standard JSON constant found: {value}")
# ---------------------------------------------------------------------------
# Configuration and disabled history
# ---------------------------------------------------------------------------
def test_engine_rejects_missing_research_evaluator(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(
        history,
        research_evaluator=None,
        max_generations=1,
    )
    engine.research_evaluator = None
    with pytest.raises(ResearchEvaluatorError):
        engine.run()
def test_disabled_history_does_not_write_jsonl(
    history_path: Path,
) -> None:
    history = make_history(history_path, enabled=False)
    engine = make_engine(history, max_generations=2)
    result = engine.run()
    assert result.status == "completed"
    assert len(history.snapshots) == 2
    assert not history_path.exists()
# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
def test_research_evaluator_failure_is_reported(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    def broken_evaluator(genome: FakeGenome) -> Mapping[str, Any]:
        raise RuntimeError(f"synthetic failure for {genome.genome_id}")
    engine = make_engine(
        history,
        research_evaluator=broken_evaluator,
        max_generations=1,
        fail_fast=True,
    )
    with pytest.raises(AlphaEvolutionError, match="evaluation failed"):
        engine.run()
def test_failed_run_is_finalized_in_history(
    history_path: Path,
) -> None:
    """
    Contract test: a failed run should persist its final status.
    If this test fails, update AlphaEvolutionEngine.run() so every
    exception path calls history.finish(status="failed", error=exc)
    before re-raising the exception.
    """
    history = make_history(history_path)
    def broken_evaluator(genome: FakeGenome) -> Mapping[str, Any]:
        raise RuntimeError("integration failure")
    engine = make_engine(
        history,
        research_evaluator=broken_evaluator,
        max_generations=1,
        fail_fast=True,
    )
    with pytest.raises(AlphaEvolutionError):
        engine.run()
    summaries = [
        record for record in read_jsonl(history_path)
        if record.get("record_type") == "run_summary"
        and record.get("event") == "run_finished"
    ]
    assert summaries, (
        "Failed evolution run was not finalized in persistent history"
    )
    assert summaries[-1]["payload"]["status"] == "failed"
    assert summaries[-1]["payload"]["error_type"] is not None
def test_history_write_failure_obeys_fail_fast_policy(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=1)
    def fail_record_generation(*args, **kwargs):
        raise OSError("synthetic history write failure")
    history.record_generation = fail_record_generation  # type: ignore[method-assign]
    with pytest.raises(AlphaEvolutionError, match="persist evolution"):
        engine.run()
# ---------------------------------------------------------------------------
# API compatibility
# ---------------------------------------------------------------------------
def test_engine_constructor_accepts_injected_history(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=1)
    assert engine.history is history
def test_history_run_id_is_exposed_in_result_metadata(
    history_path: Path,
) -> None:
    history = make_history(history_path, run_id="known-test-run")
    engine = make_engine(history, max_generations=1)
    result = engine.run()
    assert result.metadata["history_run_id"] == "known-test-run"
def test_generation_report_history_contains_no_fake_live_trading(
    history_path: Path,
) -> None:
    history = make_history(history_path)
    engine = make_engine(history, max_generations=1)
    result = engine.run()
    assert result.metadata["live_trading_enabled"] is False
    assert result.metadata["history_run_id"] == history.run_id
# ---------------------------------------------------------------------------
# Repeated run behavior
# ---------------------------------------------------------------------------
def test_repeated_run_reports_only_current_call(
    tmp_path,
):
    history = EvolutionHistory(
        config=EvolutionHistoryConfig(
            output_path=str(tmp_path / "history.jsonl"),
            enabled=True,
        )
    )
    engine = make_engine(
        history,
        max_generations=2,
    )
    first = engine.run(max_generations=2)
    second = engine.run(max_generations=1)
    assert first.generations_completed == 2
    assert second.generations_completed == 1
    assert len(second.generation_reports) == 1
def test_repeated_run_continues_with_next_generation(
    tmp_path: Path,
) -> None:
    history_path = tmp_path / "history.jsonl"
    history = make_history(history_path)
    engine = make_engine(
        history,
        max_generations=2,
    )
    first = engine.run(max_generations=2)
    second = engine.run(max_generations=1)
    assert first.generations_completed == 2
    assert second.generations_completed == 1
    first_generations = [
        item["generation"]
        for item in first.generation_reports
    ]
    second_generations = [
        item["generation"]
        for item in second.generation_reports
    ]
    assert first_generations == [0, 1]
    assert second_generations == [2]
    history_records = history.load_persisted_records(
        record_type="generation",
    )
    recorded_generations = [
        record["payload"]["generation"]
        for record in history_records
    ]
    assert recorded_generations == [0, 1, 2]
    assert history.summary()["generations_recorded"] == 3
def test_repeated_run_preserves_one_run_id(
    tmp_path: Path,
) -> None:
    history_path = tmp_path / "history.jsonl"
    history = make_history(history_path)
    engine = make_engine(history, max_generations=2)
    engine.run(max_generations=2)
    engine.run(max_generations=1)
    records = read_jsonl(history_path)
    generation_records = [
        record for record in records
        if record.get("record_type") == "generation"
    ]
    assert len(generation_records) == 3
    assert {
        record["run_id"] for record in generation_records
    } == {history.run_id}
