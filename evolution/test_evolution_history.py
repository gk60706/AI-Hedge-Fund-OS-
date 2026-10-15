"""Regression tests for evolution/evolution_history.py.
Run from the project root:
    python -m pytest -q evolution/test_evolution_history.py
Verbose mode:
    python -m pytest -v evolution/test_evolution_history.py
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import pytest
from evolution.evolution_history import (
    EvolutionEvent,
    EvolutionHistory,
    EvolutionHistoryConfig,
    EvolutionHistoryIntegrityError,
    EvolutionHistorySerializationError,
    EvolutionHistoryStore,
    EvolutionRunSummary,
    GenerationSnapshot,
)
# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
@dataclass
class FakeExpression:
    text: str
    def to_string(self) -> str:
        return self.text
@dataclass
class FakeGenome:
    genome_id: str
    fitness: float | None
    expression: FakeExpression | str | None = None
    ic: float | None = None
    icir: float | None = None
    quantile_spread: float | None = None
    turnover: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    oos_ic: float | None = None
    oos_icir: float | None = None
    oos_sharpe: float | None = None
    oos_max_drawdown: float | None = None
    complexity: float | None = None
    node_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
@dataclass
class FakeGenerationReport:
    generation: int
    population_size: int
    best_fitness: float
    mean_fitness: float
    accepted_count: int = 0
    rejected_count: int = 0
    evaluation_error_count: int = 0
    unique_expression_count: int | None = None
    expression_diversity: float | None = None
    mean_complexity: float | None = None
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_history(
    tmp_path: Path,
    *,
    run_id: str = "test-run-001",
    enabled: bool = True,
    output_path: str | None = None,
    strict_loading: bool = True,
) -> EvolutionHistory:
    if output_path is None and enabled:
        output_path = str(tmp_path / "history.jsonl")
    return EvolutionHistory(
        config=EvolutionHistoryConfig(
            output_path=output_path,
            enabled=enabled,
            strict_loading=strict_loading,
        ),
        run_id=run_id,
        metadata={"strategy_version": "V3.9.3"},
    )
def make_population() -> list[FakeGenome]:
    return [
        FakeGenome(
            genome_id="alpha-001",
            fitness=0.8,
            expression=FakeExpression("rank(close / delay(close, 1) - 1)"),
            ic=0.06,
            icir=1.2,
            quantile_spread=0.03,
            turnover=0.2,
            sharpe=1.4,
            max_drawdown=-0.12,
            oos_ic=0.035,
            oos_icir=0.75,
            oos_sharpe=0.9,
            oos_max_drawdown=-0.10,
            complexity=5,
        ),
        FakeGenome(
            genome_id="alpha-002",
            fitness=0.4,
            expression=FakeExpression("rank(volume)"),
            ic=0.02,
            complexity=3,
        ),
        FakeGenome(
            genome_id="alpha-003",
            fitness=0.2,
            expression=FakeExpression("rank(close / delay(close, 1) - 1)"),
            ic=0.01,
            complexity=4,
        ),
    ]
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    assert path.exists(), f"Missing JSONL file: {path}"
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            result.append(json.loads(line))
    return result
# ---------------------------------------------------------------------------
# Configuration and model tests
# ---------------------------------------------------------------------------
def test_history_config_rejects_empty_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        EvolutionHistoryConfig(schema_version="   ")
def test_generation_snapshot_round_trip() -> None:
    snapshot = GenerationSnapshot(
        run_id="run-a",
        generation=3,
        recorded_at="2026-01-01T00:00:00+00:00",
        population_size=20,
        best_genome_id="alpha-01",
        best_expression="rank(close)",
        best_fitness=0.7,
        mean_fitness=0.3,
        expression_diversity=0.8,
        metadata={"seed": 42},
    )
    restored = GenerationSnapshot.from_dict(snapshot.to_dict())
    assert restored.run_id == snapshot.run_id
    assert restored.generation == 3
    assert restored.best_fitness == pytest.approx(0.7)
    assert restored.metadata == {"seed": 42}
def test_event_and_run_summary_are_json_compatible() -> None:
    event = EvolutionEvent(
        run_id="run-a",
        generation=1,
        event_type="mutation",
        genome_id="alpha-child",
        parent_ids=["alpha-parent"],
        metadata={"operator": "subtree"},
    )
    summary = EvolutionRunSummary(
        run_id="run-a",
        started_at="2026-01-01T00:00:00+00:00",
        status="running",
    )
    event_json = json.dumps(event.to_dict(), allow_nan=False)
    summary_json = json.dumps(summary.to_dict(), allow_nan=False)
    assert json.loads(event_json)["event_type"] == "mutation"
    assert json.loads(summary_json)["status"] == "running"
# ---------------------------------------------------------------------------
# Generation recording and metrics
# ---------------------------------------------------------------------------
def test_record_generation_extracts_best_genome_and_metrics(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    population = make_population()
    snapshot = history.record_generation(
        0,
        population=population,
    )
    assert snapshot.best_genome_id == "alpha-001"
    assert snapshot.best_expression == (
        "rank(close / delay(close, 1) - 1)"
    )
    assert snapshot.best_fitness == pytest.approx(0.8)
    assert snapshot.mean_fitness == pytest.approx(
        (0.8 + 0.4 + 0.2) / 3
    )
    assert snapshot.median_fitness == pytest.approx(0.4)
    assert snapshot.worst_fitness == pytest.approx(0.2)
    assert snapshot.best_ic == pytest.approx(0.06)
    assert snapshot.best_oos_ic == pytest.approx(0.035)
def test_record_generation_calculates_expression_diversity(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    snapshot = history.record_generation(
        0,
        population=make_population(),
    )
    # Three genomes, two unique expression strings.
    assert snapshot.unique_expression_count == 2
    assert snapshot.expression_diversity == pytest.approx(2 / 3)
def test_report_values_override_aggregate_values(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    report = FakeGenerationReport(
        generation=0,
        population_size=3,
        best_fitness=0.95,
        mean_fitness=0.65,
        accepted_count=2,
        rejected_count=1,
        evaluation_error_count=0,
        unique_expression_count=3,
        expression_diversity=1.0,
        mean_complexity=7.5,
    )
    snapshot = history.record_generation(
        0,
        population=make_population(),
        report=report,
    )
    assert snapshot.best_fitness == pytest.approx(0.95)
    assert snapshot.mean_fitness == pytest.approx(0.65)
    assert snapshot.accepted_count == 2
    assert snapshot.rejected_count == 1
    assert snapshot.unique_expression_count == 3
    assert snapshot.expression_diversity == pytest.approx(1.0)
    assert snapshot.mean_complexity == pytest.approx(7.5)
def test_generation_improvement_and_stagnation_tracking(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    first = history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.5, "rank(close)"),
    )
    second = history.record_generation(
        1,
        best_genome=FakeGenome("b", 0.7, "rank(volume)"),
    )
    third = history.record_generation(
        2,
        best_genome=FakeGenome("c", 0.7, "rank(open)"),
    )
    assert first.improvement_from_previous is None
    assert first.stagnant_generations == 0
    assert second.improvement_from_previous == pytest.approx(0.2)
    assert second.stagnant_generations == 0
    assert third.improvement_from_previous == pytest.approx(0.0)
    assert third.stagnant_generations == 1
def test_invalid_generation_number_is_rejected(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    with pytest.raises(ValueError, match="generation"):
        history.record_generation(-1)
def test_empty_population_can_be_recorded(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    snapshot = history.record_generation(0, population=[])
    assert snapshot.population_size == 0
    assert snapshot.best_genome_id is None
    assert snapshot.best_fitness is None
    assert snapshot.mean_fitness is None
    assert snapshot.expression_diversity is None
def test_non_finite_fitness_values_are_ignored(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    population = [
        FakeGenome("a", float("nan"), "rank(close)"),
        FakeGenome("b", float("inf"), "rank(volume)"),
        FakeGenome("c", 0.25, "rank(open)"),
    ]
    snapshot = history.record_generation(0, population=population)
    assert snapshot.best_genome_id == "c"
    assert snapshot.best_fitness == pytest.approx(0.25)
    assert snapshot.evaluated_count == 1
def test_missing_metrics_remain_none(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    snapshot = history.record_generation(
        0,
        best_genome=FakeGenome(
            genome_id="alpha-no-metrics",
            fitness=0.5,
            expression=None,
        ),
    )
    assert snapshot.best_ic is None
    assert snapshot.best_oos_ic is None
    assert snapshot.best_sharpe is None
    assert snapshot.best_expression is None
def test_generation_metadata_is_preserved(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    snapshot = history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.5, "rank(close)"),
        metrics={"train_ic": 0.03},
        metadata={"source": "unit_test"},
    )
    assert snapshot.metrics["train_ic"] == pytest.approx(0.03)
    assert snapshot.metadata["source"] == "unit_test"
# ---------------------------------------------------------------------------
# Event recording and filtering
# ---------------------------------------------------------------------------
def test_record_event_extracts_genome_details(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    child = FakeGenome(
        genome_id="alpha-child",
        fitness=0.62,
        expression=FakeExpression("rank(close)"),
    )
    event = history.record_event(
        "mutation",
        generation=2,
        genome=child,
        parent_ids=["alpha-parent"],
        reason="subtree_mutation",
    )
    assert event.event_type == "mutation"
    assert event.genome_id == "alpha-child"
    assert event.parent_ids == ["alpha-parent"]
    assert event.expression == "rank(close)"
    assert event.fitness == pytest.approx(0.62)
    assert event.reason == "subtree_mutation"
def test_event_filtering_by_generation_type_and_genome(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    history.record_event(
        "mutation",
        generation=1,
        genome_id="alpha-a",
    )
    history.record_event(
        "crossover",
        generation=1,
        genome_id="alpha-b",
    )
    history.record_event(
        "mutation",
        generation=2,
        genome_id="alpha-a",
    )
    assert len(history.get_events(generation=1)) == 2
    assert len(history.get_events(event_type="mutation")) == 2
    assert len(history.get_events(genome_id="alpha-a")) == 2
    filtered = history.get_events(
        generation=1,
        event_type="crossover",
        genome_id="alpha-b",
    )
    assert len(filtered) == 1
def test_empty_event_type_is_rejected(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    with pytest.raises(ValueError, match="event_type"):
        history.record_event("", generation=0)
def test_lifecycle_helper_records_parent_ids(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    child = FakeGenome("child", 0.6, "rank(close)")
    event = history.record_genome_lifecycle(
        "crossover",
        child,
        generation=3,
        parent_ids=["parent-1", "parent-2"],
    )
    assert event.genome_id == "child"
    assert event.parent_ids == ["parent-1", "parent-2"]
# ---------------------------------------------------------------------------
# Run lifecycle and summaries
# ---------------------------------------------------------------------------
def test_finish_records_completed_status(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.8, "rank(close)"),
    )
    summary = history.finish(
        status="completed",
        stop_reason="max_generations_reached",
    )
    assert summary.status == "completed"
    assert summary.stop_reason == "max_generations_reached"
    assert summary.generations_completed == 1
    assert summary.best_genome_id == "a"
    assert summary.best_fitness == pytest.approx(0.8)
    assert summary.finished_at is not None
def test_finish_records_failure_details(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    error = RuntimeError("synthetic failure")
    summary = history.finish(
        status="failed",
        stop_reason="evaluation_error",
        error=error,
    )
    assert summary.status == "failed"
    assert summary.error_type == "RuntimeError"
    assert summary.error_message == "synthetic failure"
def test_finish_rejects_unknown_status(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    with pytest.raises(ValueError, match="status"):
        history.finish(status="unknown")
def test_summary_and_fitness_trend(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.4, "rank(close)"),
    )
    history.record_generation(
        1,
        best_genome=FakeGenome("b", 0.8, "rank(volume)"),
    )
    history.record_event(
        "mutation",
        generation=1,
        genome_id="b",
    )
    summary = history.summary()
    trend = history.fitness_trend()
    assert summary["generations_recorded"] == 2
    assert summary["events_recorded"] == 1
    assert summary["best_generation"] == 1
    assert summary["best_fitness"] == pytest.approx(0.8)
    assert len(trend) == 2
    assert trend[0]["best_fitness"] == pytest.approx(0.4)
    assert trend[1]["best_fitness"] == pytest.approx(0.8)
# ---------------------------------------------------------------------------
# Persistence and loading
# ---------------------------------------------------------------------------
def test_history_appends_generation_event_and_summary_records(
    tmp_path: Path,
) -> None:
    output = tmp_path / "persisted.jsonl"
    history = make_history(
        tmp_path,
        output_path=str(output),
    )
    history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.5, "rank(close)"),
    )
    history.record_event(
        "mutation",
        generation=1,
        genome_id="b",
    )
    history.finish(status="completed")
    records = read_jsonl(output)
    record_types = [record["record_type"] for record in records]
    assert record_types.count("run_summary") == 2
    assert record_types.count("generation") == 1
    assert record_types.count("event") == 1
    assert all(record["run_id"] == history.run_id for record in records)
    assert all(record["record_hash"] for record in records)
def test_load_persisted_records_filters_by_type(
    tmp_path: Path,
) -> None:
    output = tmp_path / "records.jsonl"
    history = make_history(
        tmp_path,
        output_path=str(output),
    )
    history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.5, "rank(close)"),
    )
    history.record_event(
        "mutation",
        generation=1,
        genome_id="b",
    )
    generations = history.load_persisted_records(
        record_type="generation"
    )
    events = history.load_persisted_records(record_type="event")
    assert len(generations) == 1
    assert len(events) == 1
    assert generations[0]["payload"]["generation"] == 0
    assert events[0]["payload"]["event_type"] == "mutation"
def test_store_filters_records_by_run_id_and_record_type(
    tmp_path: Path,
) -> None:
    output = tmp_path / "shared.jsonl"
    store = EvolutionHistoryStore(output)
    store.append({
        "run_id": "run-a",
        "record_type": "generation",
        "payload": {"generation": 0},
    })
    store.append({
        "run_id": "run-b",
        "record_type": "generation",
        "payload": {"generation": 1},
    })
    store.append({
        "run_id": "run-a",
        "record_type": "event",
        "payload": {"event_type": "mutation"},
    })
    records = store.load(
        run_id="run-a",
        record_type="generation",
    )
    assert len(records) == 1
    assert records[0]["payload"]["generation"] == 0
def test_store_returns_empty_list_for_missing_file(
    tmp_path: Path,
) -> None:
    store = EvolutionHistoryStore(tmp_path / "missing.jsonl")
    assert store.load() == []
def test_strict_loading_rejects_corrupt_jsonl(
    tmp_path: Path,
) -> None:
    output = tmp_path / "corrupt.jsonl"
    output.write_text(
        '{"record_type":"event"}\n'
        '{"record_type": broken-json}\n',
        encoding="utf-8",
    )
    store = EvolutionHistoryStore(output)
    with pytest.raises(
        EvolutionHistoryIntegrityError,
        match="line 2",
    ):
        store.load(strict=True)
def test_non_strict_loading_skips_corrupt_lines(
    tmp_path: Path,
) -> None:
    output = tmp_path / "partially_corrupt.jsonl"
    output.write_text(
        '{"run_id":"run-a","record_type":"event"}\n'
        '{"run_id": broken-json}\n'
        '{"run_id":"run-b","record_type":"event"}\n',
        encoding="utf-8",
    )
    store = EvolutionHistoryStore(output)
    records = store.load(strict=False)
    assert len(records) == 2
def test_disabled_history_does_not_create_file(
    tmp_path: Path,
) -> None:
    output = tmp_path / "disabled.jsonl"
    history = make_history(
        tmp_path,
        enabled=False,
        output_path=str(output),
    )
    history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.5, "rank(close)"),
    )
    history.finish(status="completed")
    assert not output.exists()
    assert history.summary()["generations_recorded"] == 1
def test_multiple_runs_share_file_without_cross_contamination(
    tmp_path: Path,
) -> None:
    output = tmp_path / "shared_history.jsonl"
    first = make_history(
        tmp_path,
        run_id="run-one",
        output_path=str(output),
    )
    second = make_history(
        tmp_path,
        run_id="run-two",
        output_path=str(output),
    )
    first.record_generation(
        0,
        best_genome=FakeGenome("a", 0.6, "rank(close)"),
    )
    second.record_generation(
        0,
        best_genome=FakeGenome("b", 0.9, "rank(volume)"),
    )
    first_records = first.load_persisted_records(
        record_type="generation"
    )
    second_records = second.load_persisted_records(
        record_type="generation"
    )
    assert len(first_records) == 1
    assert len(second_records) == 1
    assert first_records[0]["run_id"] == "run-one"
    assert second_records[0]["run_id"] == "run-two"
# ---------------------------------------------------------------------------
# JSON safety and data integrity
# ---------------------------------------------------------------------------
def test_non_finite_metrics_are_persisted_as_null(
    tmp_path: Path,
) -> None:
    output = tmp_path / "non_finite.jsonl"
    history = make_history(
        tmp_path,
        output_path=str(output),
    )
    history.record_generation(
        0,
        best_genome=FakeGenome(
            genome_id="a",
            fitness=0.5,
            expression="rank(close)",
            ic=float("nan"),
            oos_ic=float("inf"),
        ),
        metrics={
            "nan_metric": float("nan"),
            "infinite_metric": float("inf"),
        },
    )
    records = read_jsonl(output)
    generation_record = next(
        item for item in records
        if item["record_type"] == "generation"
    )
    payload = generation_record["payload"]
    assert payload["best_ic"] is None
    assert payload["best_oos_ic"] is None
    assert payload["metrics"]["nan_metric"] is None
    assert payload["metrics"]["infinite_metric"] is None
def test_record_hash_is_sha256_length(
    tmp_path: Path,
) -> None:
    output = tmp_path / "hashes.jsonl"
    history = make_history(
        tmp_path,
        output_path=str(output),
    )
    history.record_event(
        "selection",
        generation=0,
        genome_id="alpha-a",
    )
    records = read_jsonl(output)
    event_record = next(
        item for item in records
        if item["record_type"] == "event"
    )
    assert len(event_record["record_hash"]) == 64
    assert all(
        character in "0123456789abcdef"
        for character in event_record["record_hash"]
    )
def test_persisted_jsonl_is_strictly_valid_json(
    tmp_path: Path,
) -> None:
    output = tmp_path / "strict.jsonl"
    history = make_history(
        tmp_path,
        output_path=str(output),
    )
    history.record_generation(
        0,
        best_genome=FakeGenome(
            "a",
            0.5,
            "rank(close)",
            ic=float("nan"),
        ),
    )
    for line in output.read_text(encoding="utf-8").splitlines():
        json.loads(line, parse_constant=lambda value: (
            _raise_invalid_constant(value)
        ))
def _raise_invalid_constant(value: str) -> None:
    raise AssertionError(f"Non-standard JSON constant found: {value}")
def test_duplicate_generation_numbers_are_currently_allowed(
    tmp_path: Path,
) -> None:
    history = make_history(tmp_path)
    first = history.record_generation(
        0,
        best_genome=FakeGenome("a", 0.5, "rank(close)"),
    )
    second = history.record_generation(
        0,
        best_genome=FakeGenome("b", 0.6, "rank(volume)"),
    )
    assert first.generation == second.generation == 0
    assert len(history.snapshots) == 2
