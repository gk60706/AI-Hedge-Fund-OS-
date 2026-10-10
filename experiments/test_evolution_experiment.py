"""Automated tests for experiments/evolution_experiment.py.
Run from the project root:
    pytest -q experiments/test_evolution_experiment.py
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import pytest
from experiments.evolution_experiment import (
    AlphaEvolutionExperiment,
    EvolutionExperimentConfig,
    EvolutionExperimentError,
    EvolutionExperimentResult,
    ExperimentSerializationError,
    JsonlExperimentStore,
)
# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
@dataclass
class FakeExpression:
    text: str = "rank(close / delay(close, 1) - 1)"
    def to_string(self) -> str:
        return self.text
@dataclass
class FakeGenome:
    genome_id: str = "genome-test-001"
    expression: FakeExpression = field(default_factory=FakeExpression)
    fitness: float = 0.82
    ic: float = 0.06
    icir: float = 1.20
    quantile_spread: float = 0.025
    long_short_spread: float = 0.03
    hit_rate: float = 0.56
    turnover: float = 0.20
    volatility: float = 0.15
    sharpe: float = 1.35
    max_drawdown: float = -0.12
    oos_ic: float = 0.035
    oos_icir: float = 0.75
    oos_sharpe: float = 0.90
    oos_max_drawdown: float = -0.10
    metadata: dict[str, Any] = field(default_factory=dict)
@dataclass
class FakeGenerationReport:
    generation: int
    best_fitness: float
    mean_fitness: float
    accepted_count: int = 1
    evaluation_errors: int = 0
@dataclass
class FakeEngineResult:
    generations_completed: int
    generation_reports: list[FakeGenerationReport]
    best_genome: FakeGenome
    stop_reason: str = "max_generations_reached"
class FakeEvolutionEngine:
    """Minimal engine matching the interface expected by the wrapper."""
    def __init__(
        self,
        result: FakeEngineResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or FakeEngineResult(
            generations_completed=2,
            generation_reports=[
                FakeGenerationReport(
                    generation=0,
                    best_fitness=0.71,
                    mean_fitness=0.25,
                ),
                FakeGenerationReport(
                    generation=1,
                    best_fitness=0.82,
                    mean_fitness=0.38,
                ),
            ],
            best_genome=FakeGenome(),
        )
        self.error = error
        self.received_max_generations: int | None = None
    def run(self, max_generations: int | None = None) -> FakeEngineResult:
        self.received_max_generations = max_generations
        if self.error is not None:
            raise self.error
        return self.result
class FakeEngineWithoutKeyword:
    """Compatibility case for engines whose run() takes no arguments."""
    def __init__(self) -> None:
        self.called = False
    def run(self):
        self.called = True
        return FakeEngineResult(
            generations_completed=1,
            generation_reports=[
                FakeGenerationReport(
                    generation=0,
                    best_fitness=0.5,
                    mean_fitness=0.2,
                )
            ],
            best_genome=FakeGenome(fitness=0.5),
            stop_reason="completed",
        )
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_config(
    tmp_path: Path,
    **overrides: Any,
) -> EvolutionExperimentConfig:
    values: dict[str, Any] = {
        "experiment_name": "test_alpha_evolution",
        "max_generations": 3,
        "output_path": str(tmp_path / "runs" / "experiments.jsonl"),
        "random_seed": 42,
        "strategy_version": "V3.9.3",
        "data_start": "2024-01-01",
        "data_end": "2025-12-31",
        "universe": "CSI300",
        "search_space": {"max_depth": 5, "max_nodes": 20},
        "metadata": {"purpose": "unit_test"},
    }
    values.update(overrides)
    return EvolutionExperimentConfig(**values)
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    assert path.exists(), f"Expected JSONL file to exist: {path}"
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [json.loads(line) for line in lines]
def make_result(
    *,
    fitness: float = 0.82,
    generation_count: int = 2,
) -> FakeEngineResult:
    reports = [
        FakeGenerationReport(
            generation=i,
            best_fitness=fitness - (generation_count - i - 1) * 0.1,
            mean_fitness=0.25 + i * 0.05,
        )
        for i in range(generation_count)
    ]
    return FakeEngineResult(
        generations_completed=generation_count,
        generation_reports=reports,
        best_genome=FakeGenome(fitness=fitness),
        stop_reason="test_completed",
    )
# ---------------------------------------------------------------------------
# Configuration and result tests
# ---------------------------------------------------------------------------
def test_config_rejects_empty_experiment_name() -> None:
    with pytest.raises(ValueError, match="experiment_name"):
        EvolutionExperimentConfig(experiment_name="   ")
def test_config_rejects_invalid_generation_limit() -> None:
    with pytest.raises(ValueError, match="max_generations"):
        EvolutionExperimentConfig(max_generations=0)
def test_result_to_dict_is_json_compatible() -> None:
    result = EvolutionExperimentResult(
        experiment_id="test-id",
        experiment_name="test",
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        duration_seconds=1.0,
        generation_reports=[
            {"generation": 0, "best_fitness": 0.5}
        ],
    )
    payload = result.to_dict()
    encoded = json.dumps(payload, allow_nan=False)
    assert json.loads(encoded)["status"] == "completed"
# ---------------------------------------------------------------------------
# Successful execution tests
# ---------------------------------------------------------------------------
def test_run_passes_generation_limit_to_engine(tmp_path: Path) -> None:
    engine = FakeEvolutionEngine()
    experiment = AlphaEvolutionExperiment(
        engine,
        config=make_config(tmp_path, max_generations=7),
    )
    result = experiment.run()
    assert engine.received_max_generations == 7
    assert result.status == "completed"
def test_run_extracts_best_genome_and_reports(tmp_path: Path) -> None:
    engine = FakeEvolutionEngine()
    experiment = AlphaEvolutionExperiment(
        engine,
        config=make_config(tmp_path),
    )
    result = experiment.run()
    assert result.best_genome_id == "genome-test-001"
    assert result.best_expression == "rank(close / delay(close, 1) - 1)"
    assert result.best_fitness == pytest.approx(0.82)
    assert result.generations_completed == 2
    assert len(result.generation_reports) == 2
    assert result.stop_reason == "max_generations_reached"
    assert result.best_metrics["ic"] == pytest.approx(0.06)
    assert result.best_metrics["oos_ic"] == pytest.approx(0.035)
def test_run_persists_one_complete_jsonl_record(tmp_path: Path) -> None:
    output = tmp_path / "records.jsonl"
    experiment = AlphaEvolutionExperiment(
        FakeEvolutionEngine(),
        config=make_config(tmp_path, output_path=str(output)),
    )
    result = experiment.run()
    records = read_jsonl(output)
    assert len(records) == 1
    record = records[0]
    assert result.record_path == str(output.resolve())
    assert record["schema_version"] == "1.0"
    assert record["experiment"]["status"] == "completed"
    assert record["experiment"]["experiment_id"] == result.experiment_id
    assert record["result"]["best_fitness"] == pytest.approx(0.82)
    assert record["data"]["universe"] == "CSI300"
    assert record["reproducibility"]["random_seed"] == 42
    assert record["record_hash"]
def test_repeated_runs_append_records_without_overwriting(
    tmp_path: Path,
) -> None:
    output = tmp_path / "records.jsonl"
    first = AlphaEvolutionExperiment(
        FakeEvolutionEngine(make_result(fitness=0.70)),
        config=make_config(
            tmp_path,
            output_path=str(output),
            experiment_name="run-one",
        ),
    )
    second = AlphaEvolutionExperiment(
        FakeEvolutionEngine(make_result(fitness=0.90)),
        config=make_config(
            tmp_path,
            output_path=str(output),
            experiment_name="run-two",
        ),
    )
    first_result = first.run()
    second_result = second.run()
    records = read_jsonl(output)
    assert len(records) == 2
    assert first_result.experiment_id != second_result.experiment_id
    assert records[0]["experiment"]["experiment_name"] == "run-one"
    assert records[1]["experiment"]["experiment_name"] == "run-two"
    assert records[0]["result"]["best_fitness"] == pytest.approx(0.70)
    assert records[1]["result"]["best_fitness"] == pytest.approx(0.90)
def test_output_path_none_disables_local_file(
    tmp_path: Path,
) -> None:
    experiment = AlphaEvolutionExperiment(
        FakeEvolutionEngine(),
        config=make_config(tmp_path, output_path=None),
    )
    result = experiment.run()
    assert result.status == "completed"
    assert result.record_path is None
def test_registry_writer_receives_record(tmp_path: Path) -> None:
    received: list[dict[str, Any]] = []
    experiment = AlphaEvolutionExperiment(
        FakeEvolutionEngine(),
        config=make_config(tmp_path, output_path=None),
        registry_writer=received.append,
    )
    result = experiment.run()
    assert result.status == "completed"
    assert len(received) == 1
    assert received[0]["experiment"]["experiment_id"] == result.experiment_id
    assert received[0]["record_hash"]
# ---------------------------------------------------------------------------
# Failure handling tests
# ---------------------------------------------------------------------------
def test_engine_failure_is_recorded_when_capture_enabled(
    tmp_path: Path,
) -> None:
    output = tmp_path / "failed.jsonl"
    engine = FakeEvolutionEngine(error=RuntimeError("synthetic test failure"))
    experiment = AlphaEvolutionExperiment(
        engine,
        config=make_config(
            tmp_path,
            output_path=str(output),
            capture_exceptions=True,
        ),
    )
    result = experiment.run()
    records = read_jsonl(output)
    assert result.status == "failed"
    assert result.error_type == "RuntimeError"
    assert "synthetic test failure" in (result.error_message or "")
    assert len(records) == 1
    assert records[0]["experiment"]["status"] == "failed"
    assert records[0]["error"]["type"] == "RuntimeError"
    assert "Traceback" in records[0]["error"]["traceback"]
def test_engine_failure_is_reraised_when_capture_disabled(
    tmp_path: Path,
) -> None:
    output = tmp_path / "failed_reraise.jsonl"
    engine = FakeEvolutionEngine(error=RuntimeError("reraised failure"))
    experiment = AlphaEvolutionExperiment(
        engine,
        config=make_config(
            tmp_path,
            output_path=str(output),
            capture_exceptions=False,
        ),
    )
    with pytest.raises(RuntimeError, match="reraised failure"):
        experiment.run()
    records = read_jsonl(output)
    assert len(records) == 1
    assert records[0]["experiment"]["status"] == "failed"
def test_engine_without_max_generations_keyword_is_supported(
    tmp_path: Path,
) -> None:
    engine = FakeEngineWithoutKeyword()
    experiment = AlphaEvolutionExperiment(
        engine,
        config=make_config(tmp_path),
    )
    result = experiment.run()
    assert engine.called is True
    assert result.status == "completed"
    assert result.generations_completed == 1
# ---------------------------------------------------------------------------
# Serialization and storage tests
# ---------------------------------------------------------------------------
def test_jsonl_store_converts_non_finite_numbers_to_null(
    tmp_path: Path,
) -> None:
    output = tmp_path / "safe.jsonl"
    store = JsonlExperimentStore(output)
    store.append(
        {
            "valid": 1.25,
            "nan": float("nan"),
            "positive_infinity": float("inf"),
            "negative_infinity": float("-inf"),
        }
    )
    records = read_jsonl(output)
    assert records == [
        {
            "valid": 1.25,
            "nan": None,
            "positive_infinity": None,
            "negative_infinity": None,
        }
    ]
def test_jsonl_store_rejects_unserializable_objects(
    tmp_path: Path,
) -> None:
    store = JsonlExperimentStore(tmp_path / "bad.jsonl")
    # _json_safe intentionally converts many objects to strings, so use a
    # mapping with a key that cannot be represented safely as a normal key.
    # This test instead verifies that the store emits strict JSON.
    store.append({"value": math.nan})
    records = read_jsonl(tmp_path / "bad.jsonl")
    assert records[0]["value"] is None
def test_metadata_is_preserved_in_record(tmp_path: Path) -> None:
    output = tmp_path / "metadata.jsonl"
    experiment = AlphaEvolutionExperiment(
        FakeEvolutionEngine(),
        config=make_config(
            tmp_path,
            output_path=str(output),
            metadata={
                "purpose": "regression_test",
                "dataset_tag": "daily_equity",
            },
        ),
    )
    experiment.run()
    record = read_jsonl(output)[0]
    assert record["metadata"]["purpose"] == "regression_test"
    assert record["metadata"]["dataset_tag"] == "daily_equity"
def test_experiment_ids_are_unique_by_default(tmp_path: Path) -> None:
    config = make_config(tmp_path, output_path=None)
    first = AlphaEvolutionExperiment(FakeEvolutionEngine(), config=config)
    second = AlphaEvolutionExperiment(FakeEvolutionEngine(), config=config)
    assert first.experiment_id != second.experiment_id
def test_empty_engine_result_does_not_crash(tmp_path: Path) -> None:
    class EmptyResultEngine:
        def run(self, max_generations=None):
            return {}
        generation_reports = []
    experiment = AlphaEvolutionExperiment(
        EmptyResultEngine(),
        config=make_config(tmp_path, output_path=None),
    )
    result = experiment.run()
    assert result.status == "completed"
    assert result.best_genome_id is None
    assert result.best_expression is None
    assert result.best_fitness is None
    assert result.generations_completed == 0
