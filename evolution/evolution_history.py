"""
AI Hedge Fund OS - V3.9.3
File: evolution/evolution_history.py
Purpose
-------
Record, persist, query, and restore Alpha Evolution history.
Features
--------
- Generation-level snapshots
- Best/mean/worst fitness and diversity tracking
- Alpha lineage and lifecycle events
- Training and out-of-sample (OOS) metrics
- Append-only JSONL persistence
- History loading and filtering
- Fitness trend summaries
- No API key access and no live-trading functionality
Python: 3.11+
"""
from __future__ import annotations
import dataclasses
import hashlib
import json
import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence
logger = logging.getLogger(__name__)
JsonDict = dict[str, Any]
# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class EvolutionHistoryError(RuntimeError):
    """Base exception for evolution history operations."""
class EvolutionHistorySerializationError(EvolutionHistoryError):
    """Raised when a history record cannot be serialized."""
class EvolutionHistoryIntegrityError(EvolutionHistoryError):
    """Raised when a persisted history record is invalid."""
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class EvolutionHistoryConfig:
    """Configuration for evolution history persistence."""
    output_path: Optional[str] = (
        "experiments/runs/evolution_history.jsonl"
    )
    enabled: bool = True
    flush_each_record: bool = True
    strict_loading: bool = True
    schema_version: str = "1.0"
    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")
# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class GenerationSnapshot:
    """Summary of one evaluated Alpha population generation."""
    run_id: str
    generation: int
    recorded_at: str
    population_size: int = 0
    evaluated_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    evaluation_error_count: int = 0
    best_genome_id: Optional[str] = None
    best_expression: Optional[str] = None
    best_fitness: Optional[float] = None
    mean_fitness: Optional[float] = None
    median_fitness: Optional[float] = None
    worst_fitness: Optional[float] = None
    fitness_std: Optional[float] = None
    unique_expression_count: Optional[int] = None
    expression_diversity: Optional[float] = None
    mean_complexity: Optional[float] = None
    best_ic: Optional[float] = None
    best_icir: Optional[float] = None
    best_quantile_spread: Optional[float] = None
    best_turnover: Optional[float] = None
    best_sharpe: Optional[float] = None
    best_max_drawdown: Optional[float] = None
    best_oos_ic: Optional[float] = None
    best_oos_icir: Optional[float] = None
    best_oos_sharpe: Optional[float] = None
    best_oos_max_drawdown: Optional[float] = None
    improvement_from_previous: Optional[float] = None
    stagnant_generations: int = 0
    stop_reason: Optional[str] = None
    metrics: JsonDict = field(default_factory=dict)
    metadata: JsonDict = field(default_factory=dict)
    def to_dict(self) -> JsonDict:
        return _json_safe(dataclasses.asdict(self))
    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GenerationSnapshot":
        allowed = {item.name for item in dataclasses.fields(cls)}
        payload = {key: value for key, value in data.items() if key in allowed}
        return cls(**payload)
@dataclass(slots=True)
class EvolutionEvent:
    """An event occurring during Alpha evolution."""
    run_id: str
    generation: int
    event_type: str
    recorded_at: str = field(default_factory=_utc_now)
    genome_id: Optional[str] = None
    parent_ids: list[str] = field(default_factory=list)
    expression: Optional[str] = None
    reason: Optional[str] = None
    fitness: Optional[float] = None
    metadata: JsonDict = field(default_factory=dict)
    def to_dict(self) -> JsonDict:
        return _json_safe(dataclasses.asdict(self))
@dataclass(slots=True)
class EvolutionRunSummary:
    """Summary for a complete or partially completed evolution run."""
    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    status: str = "running"
    generations_completed: int = 0
    best_genome_id: Optional[str] = None
    best_expression: Optional[str] = None
    best_fitness: Optional[float] = None
    best_oos_ic: Optional[float] = None
    stop_reason: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    metadata: JsonDict = field(default_factory=dict)
    def to_dict(self) -> JsonDict:
        return _json_safe(dataclasses.asdict(self))
# ---------------------------------------------------------------------------
# JSONL store
# ---------------------------------------------------------------------------
class EvolutionHistoryStore:
    """
    Append-only JSONL store.
    One line equals one complete history record. This is convenient for
    auditing and replay, but it is not a transactional database. For
    multi-process writers, use a database or external locking service.
    """
    def __init__(
        self,
        path: str | Path,
        *,
        flush_each_record: bool = True,
    ) -> None:
        self.path = Path(path)
        self.flush_each_record = flush_each_record
        self._lock = threading.Lock()
    def append(self, record: Mapping[str, Any]) -> str:
        """Append a record and return the absolute path."""
        safe_record = _json_safe(dict(record))
        try:
            line = json.dumps(
                safe_record,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise EvolutionHistorySerializationError(
                f"Could not serialize history record: {exc}"
            ) from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                if self.flush_each_record:
                    handle.flush()
        return str(self.path.resolve())
    def load(
        self,
        *,
        run_id: Optional[str] = None,
        record_type: Optional[str] = None,
        strict: bool = True,
    ) -> list[JsonDict]:
        """Load records, optionally filtered by run ID and record type."""
        if not self.path.exists():
            return []
        records: list[JsonDict] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                try:
                    record = json.loads(raw_line)
                    if not isinstance(record, dict):
                        raise ValueError("record must be a JSON object")
                except (json.JSONDecodeError, ValueError) as exc:
                    message = (
                        f"Invalid JSONL record at line {line_number}: {exc}"
                    )
                    if strict:
                        raise EvolutionHistoryIntegrityError(message) from exc
                    logger.warning(message)
                    continue
                if run_id is not None and record.get("run_id") != run_id:
                    continue
                if (
                    record_type is not None
                    and record.get("record_type") != record_type
                ):
                    continue
                records.append(record)
        return records
# ---------------------------------------------------------------------------
# Main history manager
# ---------------------------------------------------------------------------
class EvolutionHistory:
    """
    Manage generation snapshots, lifecycle events, and run summaries.
    The manager accepts plain mappings and common object-based report/genome
    interfaces to reduce coupling to the implementation of the population
    and evolution engine.
    """
    def __init__(
        self,
        config: Optional[EvolutionHistoryConfig] = None,
        *,
        run_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.config = config or EvolutionHistoryConfig()
        self.run_id = run_id or str(uuid.uuid4())
        self.metadata = _json_safe(dict(metadata or {}))
        self.snapshots: list[GenerationSnapshot] = []
        self.events: list[EvolutionEvent] = []
        self.run_summary = EvolutionRunSummary(
            run_id=self.run_id,
            started_at=_utc_now(),
            metadata=dict(self.metadata),
        )
        self.store: Optional[EvolutionHistoryStore] = None
        if self.config.enabled and self.config.output_path:
            self.store = EvolutionHistoryStore(
                self.config.output_path,
                flush_each_record=self.config.flush_each_record,
            )
        self._lock = threading.RLock()
        self._last_best_fitness: Optional[float] = None
        self._stagnant_generations = 0
        self._persist_run_summary("run_started")
    # ------------------------------------------------------------------
    # Public recording methods
    # ------------------------------------------------------------------
    def record_generation(
        self,
        generation: int,
        *,
        population: Optional[Iterable[Any]] = None,
        report: Any = None,
        best_genome: Any = None,
        metrics: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        stop_reason: Optional[str] = None,
    ) -> GenerationSnapshot:
        """
        Record one generation.
        Values from an explicit report take precedence for aggregate metrics.
        If no best genome is supplied, the best finite-fitness genome is
        selected from the population when possible.
        """
        if generation < 0:
            raise ValueError("generation must be >= 0")
        individuals = list(population) if population is not None else []
        if best_genome is None:
            best_genome = _find_best_genome(individuals)
        aggregate = _aggregate_population(individuals)
        report_values = _object_to_dict(report)
        best_values = _genome_metrics(best_genome)
        best_id, expression, fitness = _genome_identity(best_genome)
        best_fitness = _first_float(
            report_values,
            ("best_fitness", "best_score"),
        )
        if best_fitness is None:
            best_fitness = fitness
        previous = self._last_best_fitness
        improvement: Optional[float] = None
        if best_fitness is not None and previous is not None:
            improvement = best_fitness - previous
            if improvement > 0:
                self._stagnant_generations = 0
            else:
                self._stagnant_generations += 1
        elif best_fitness is not None:
            self._stagnant_generations = 0
        if best_fitness is not None:
            self._last_best_fitness = best_fitness
        snapshot = GenerationSnapshot(
            run_id=self.run_id,
            generation=generation,
            recorded_at=_utc_now(),
            population_size=_first_int(
                report_values,
                ("population_size",),
            ) or len(individuals),
            evaluated_count=_first_int(
                report_values,
                ("evaluated_count", "finite_fitness_count"),
            ) or aggregate.get("finite_fitness_count", 0),
            accepted_count=_first_int(
                report_values,
                ("accepted_count", "accepted"),
            ) or 0,
            rejected_count=_first_int(
                report_values,
                ("rejected_count", "rejected"),
            ) or 0,
            evaluation_error_count=_first_int(
                report_values,
                ("evaluation_error_count", "error_count"),
            ) or 0,
            best_genome_id=best_id,
            best_expression=expression,
            best_fitness=best_fitness,
            mean_fitness=_first_float(
                report_values,
                ("mean_fitness",),
            ),
            median_fitness=aggregate.get("median_fitness"),
            worst_fitness=aggregate.get("worst_fitness"),
            fitness_std=aggregate.get("fitness_std"),
            unique_expression_count=_first_int(
                report_values,
                ("unique_expression_count",),
            ),
            expression_diversity=_first_float(
                report_values,
                ("expression_diversity", "diversity"),
            ),
            mean_complexity=_first_float(
                report_values,
                ("mean_complexity",),
            ),
            best_ic=_metric_from(best_values, "ic"),
            best_icir=_metric_from(best_values, "icir"),
            best_quantile_spread=_metric_from(
                best_values,
                "quantile_spread",
            ),
            best_turnover=_metric_from(best_values, "turnover"),
            best_sharpe=_metric_from(best_values, "sharpe"),
            best_max_drawdown=_metric_from(best_values, "max_drawdown"),
            best_oos_ic=_metric_from(best_values, "oos_ic"),
            best_oos_icir=_metric_from(best_values, "oos_icir"),
            best_oos_sharpe=_metric_from(best_values, "oos_sharpe"),
            best_oos_max_drawdown=_metric_from(
                best_values,
                "oos_max_drawdown",
            ),
            improvement_from_previous=improvement,
            stagnant_generations=self._stagnant_generations,
            stop_reason=stop_reason,
            metrics=_json_safe(dict(metrics or {})),
            metadata=_json_safe(dict(metadata or {})),
        )
        # Use explicit aggregate report values when present.
        if snapshot.mean_fitness is None:
            snapshot.mean_fitness = aggregate.get("mean_fitness")
        if snapshot.unique_expression_count is None:
            snapshot.unique_expression_count = aggregate.get(
                "unique_expression_count"
            )
        if snapshot.expression_diversity is None:
            snapshot.expression_diversity = aggregate.get(
                "expression_diversity"
            )
        if snapshot.mean_complexity is None:
            snapshot.mean_complexity = aggregate.get("mean_complexity")
        with self._lock:
            self.snapshots.append(snapshot)
            self.run_summary.generations_completed = len(self.snapshots)
            if best_fitness is not None and (
                self.run_summary.best_fitness is None
                or best_fitness > self.run_summary.best_fitness
            ):
                self.run_summary.best_fitness = best_fitness
                self.run_summary.best_genome_id = best_id
                self.run_summary.best_expression = expression
                self.run_summary.best_oos_ic = snapshot.best_oos_ic
            self._persist_record(
                record_type="generation",
                payload=snapshot.to_dict(),
            )
        return snapshot
    def record_event(
        self,
        event_type: str,
        *,
        generation: int,
        genome: Any = None,
        genome_id: Optional[str] = None,
        parent_ids: Optional[Sequence[str]] = None,
        expression: Optional[str] = None,
        reason: Optional[str] = None,
        fitness: Optional[float] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> EvolutionEvent:
        """Record a lifecycle event such as mutation, crossover, or removal."""
        if not event_type.strip():
            raise ValueError("event_type must not be empty")
        if generation < 0:
            raise ValueError("generation must be >= 0")
        extracted_id, extracted_expression, extracted_fitness = (
            _genome_identity(genome)
        )
        event = EvolutionEvent(
            run_id=self.run_id,
            generation=generation,
            event_type=event_type,
            genome_id=genome_id or extracted_id,
            parent_ids=[str(item) for item in (parent_ids or [])],
            expression=expression or extracted_expression,
            reason=reason,
            fitness=fitness if fitness is not None else extracted_fitness,
            metadata=_json_safe(dict(metadata or {})),
        )
        with self._lock:
            self.events.append(event)
            self._persist_record(
                record_type="event",
                payload=event.to_dict(),
            )
        return event
    def record_genome_lifecycle(
        self,
        event_type: str,
        genome: Any,
        *,
        generation: int,
        parent_ids: Optional[Sequence[str]] = None,
        reason: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> EvolutionEvent:
        """Convenience method for genome creation/selection/removal events."""
        return self.record_event(
            event_type,
            generation=generation,
            genome=genome,
            parent_ids=parent_ids,
            reason=reason,
            metadata=metadata,
        )
    def finish(
        self,
        *,
        status: str = "completed",
        stop_reason: Optional[str] = None,
        error: Optional[BaseException] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> EvolutionRunSummary:
        """Finalize the run and persist its summary."""
        allowed_statuses = {
            "completed",
            "stopped",
            "failed",
            "cancelled",
            "interrupted",
        }
        if status not in allowed_statuses:
            raise ValueError(
                f"status must be one of {sorted(allowed_statuses)}"
            )
        with self._lock:
            self.run_summary.finished_at = _utc_now()
            self.run_summary.status = status
            self.run_summary.stop_reason = stop_reason
            if error is not None:
                self.run_summary.error_type = type(error).__name__
                self.run_summary.error_message = str(error)
            if metadata:
                self.run_summary.metadata.update(_json_safe(dict(metadata)))
            self._persist_run_summary("run_finished")
        return self.run_summary
    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------
    def get_generation(
        self,
        generation: int,
    ) -> Optional[GenerationSnapshot]:
        """Return a snapshot by generation number, if present."""
        for snapshot in reversed(self.snapshots):
            if snapshot.generation == generation:
                return snapshot
        return None
    def get_events(
        self,
        *,
        generation: Optional[int] = None,
        event_type: Optional[str] = None,
        genome_id: Optional[str] = None,
    ) -> list[EvolutionEvent]:
        """Filter in-memory lifecycle events."""
        results = self.events
        if generation is not None:
            results = [
                item for item in results
                if item.generation == generation
            ]
        if event_type is not None:
            results = [
                item for item in results
                if item.event_type == event_type
            ]
        if genome_id is not None:
            results = [
                item for item in results
                if item.genome_id == genome_id
            ]
        return list(results)
    def fitness_trend(self) -> list[dict[str, Any]]:
        """Return ordered best/mean fitness observations."""
        return [
            {
                "generation": item.generation,
                "best_fitness": item.best_fitness,
                "mean_fitness": item.mean_fitness,
                "oos_ic": item.best_oos_ic,
                "expression_diversity": item.expression_diversity,
            }
            for item in self.snapshots
        ]
    def summary(self) -> JsonDict:
        """Return a compact summary of the current in-memory history."""
        best_snapshot = _best_snapshot(self.snapshots)
        return {
            "run_id": self.run_id,
            "status": self.run_summary.status,
            "generations_recorded": len(self.snapshots),
            "events_recorded": len(self.events),
            "best_generation": (
                best_snapshot.generation if best_snapshot else None
            ),
            "best_fitness": (
                best_snapshot.best_fitness if best_snapshot else None
            ),
            "best_expression": (
                best_snapshot.best_expression if best_snapshot else None
            ),
            "last_generation": (
                self.snapshots[-1].generation if self.snapshots else None
            ),
            "stagnant_generations": self._stagnant_generations,
        }
    def load_persisted_records(
        self,
        *,
        record_type: Optional[str] = None,
        strict: Optional[bool] = None,
    ) -> list[JsonDict]:
        """Load stored records for this run without mutating in-memory state."""
        if self.store is None:
            return []
        return self.store.load(
            run_id=self.run_id,
            record_type=record_type,
            strict=(
                self.config.strict_loading if strict is None else strict
            ),
        )
    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _persist_record(
        self,
        *,
        record_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        if self.store is None:
            return
        record: JsonDict = {
            "schema_version": self.config.schema_version,
            "record_type": record_type,
            "run_id": self.run_id,
            "recorded_at": _utc_now(),
            "payload": _json_safe(dict(payload)),
        }
        record["record_hash"] = _stable_hash(record)
        self.store.append(record)
    def _persist_run_summary(self, event: str) -> None:
        if self.store is None:
            return
        record: JsonDict = {
            "schema_version": self.config.schema_version,
            "record_type": "run_summary",
            "event": event,
            "run_id": self.run_id,
            "recorded_at": _utc_now(),
            "payload": self.run_summary.to_dict(),
        }
        record["record_hash"] = _stable_hash(record)
        self.store.append(record)
# ---------------------------------------------------------------------------
# Extraction and calculation helpers
# ---------------------------------------------------------------------------
def _object_to_dict(value: Any) -> JsonDict:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if dataclasses.is_dataclass(value):
        try:
            return dataclasses.asdict(value)
        except Exception:
            pass
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            result = to_dict()
            if isinstance(result, Mapping):
                return dict(result)
        except Exception:
            logger.debug("Could not convert object using to_dict()", exc_info=True)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}
def _get_value(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None) if value is not None else None
def _finite_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None
def _as_nonnegative_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number >= 0 else None
def _first_float(
    mapping: Mapping[str, Any],
    names: Sequence[str],
) -> Optional[float]:
    for name in names:
        value = _finite_float(mapping.get(name))
        if value is not None:
            return value
    return None
def _first_int(
    mapping: Mapping[str, Any],
    names: Sequence[str],
) -> Optional[int]:
    for name in names:
        value = _as_nonnegative_int(mapping.get(name))
        if value is not None:
            return value
    return None
def _genome_identity(
    genome: Any,
) -> tuple[Optional[str], Optional[str], Optional[float]]:
    if genome is None:
        return None, None, None
    genome_id = (
        _get_value(genome, "genome_id")
        or _get_value(genome, "alpha_id")
        or _get_value(genome, "id")
    )
    expression = _get_value(genome, "expression")
    expression_text: Optional[str] = None
    if expression is not None:
        to_string = getattr(expression, "to_string", None)
        if callable(to_string):
            try:
                expression_text = str(to_string())
            except Exception:
                expression_text = None
        if expression_text is None:
            if isinstance(expression, str):
                expression_text = expression
            else:
                expression_text = str(expression)
    fitness = _finite_float(_get_value(genome, "fitness"))
    return (
        str(genome_id) if genome_id is not None else None,
        expression_text,
        fitness,
    )
def _genome_metrics(genome: Any) -> JsonDict:
    if genome is None:
        return {}
    names = (
        "ic",
        "icir",
        "quantile_spread",
        "long_short_spread",
        "hit_rate",
        "turnover",
        "volatility",
        "sharpe",
        "max_drawdown",
        "oos_ic",
        "oos_icir",
        "oos_sharpe",
        "oos_max_drawdown",
        "complexity",
        "node_count",
        "depth",
    )
    result: JsonDict = {}
    for name in names:
        value = _get_value(genome, name)
        if value is not None:
            result[name] = value
    metadata = _get_value(genome, "metadata")
    if isinstance(metadata, Mapping):
        oos_metrics = metadata.get("oos_metrics")
        if isinstance(oos_metrics, Mapping):
            for name in (
                "oos_ic",
                "oos_icir",
                "oos_sharpe",
                "oos_max_drawdown",
            ):
                if name not in result and name in oos_metrics:
                    result[name] = oos_metrics[name]
    return result
def _metric_from(
    metrics: Mapping[str, Any],
    name: str,
) -> Optional[float]:
    return _finite_float(metrics.get(name))
def _find_best_genome(individuals: Sequence[Any]) -> Any:
    best = None
    best_fitness = float("-inf")
    for individual in individuals:
        fitness = _finite_float(_get_value(individual, "fitness"))
        if fitness is None:
            continue
        if fitness > best_fitness:
            best = individual
            best_fitness = fitness
    return best
def _aggregate_population(individuals: Sequence[Any]) -> JsonDict:
    values: list[float] = []
    expressions: set[str] = set()
    complexities: list[float] = []
    for individual in individuals:
        fitness = _finite_float(_get_value(individual, "fitness"))
        if fitness is not None:
            values.append(fitness)
        _, expression, _ = _genome_identity(individual)
        if expression:
            expressions.add(expression)
        complexity = _finite_float(_get_value(individual, "complexity"))
        if complexity is None:
            complexity = _finite_float(_get_value(individual, "node_count"))
        if complexity is not None:
            complexities.append(complexity)
    values.sort()
    count = len(values)
    if count:
        mean_fitness = sum(values) / count
        median_fitness = (
            values[count // 2]
            if count % 2
            else (values[count // 2 - 1] + values[count // 2]) / 2
        )
        variance = sum(
            (value - mean_fitness) ** 2 for value in values
        ) / count
        fitness_std = math.sqrt(variance)
        worst_fitness = values[0]
    else:
        mean_fitness = None
        median_fitness = None
        fitness_std = None
        worst_fitness = None
    population_size = len(individuals)
    unique_count = len(expressions)
    return {
        "population_size": population_size,
        "finite_fitness_count": count,
        "mean_fitness": mean_fitness,
        "median_fitness": median_fitness,
        "worst_fitness": worst_fitness,
        "fitness_std": fitness_std,
        "unique_expression_count": unique_count,
        "expression_diversity": (
            unique_count / population_size if population_size else None
        ),
        "mean_complexity": (
            sum(complexities) / len(complexities)
            if complexities else None
        ),
    }
def _best_snapshot(
    snapshots: Sequence[GenerationSnapshot],
) -> Optional[GenerationSnapshot]:
    candidates = [
        item for item in snapshots
        if item.best_fitness is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.best_fitness)
def _json_safe(value: Any) -> Any:
    """Convert common scientific Python values to strict JSON-compatible data."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return _json_safe(item_method())
        except Exception:
            pass
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            pass
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict())
        except Exception:
            pass
    return str(value)
def _stable_hash(record: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _json_safe(dict(record)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
__all__ = [
    "EvolutionHistoryError",
    "EvolutionHistorySerializationError",
    "EvolutionHistoryIntegrityError",
    "EvolutionHistoryConfig",
    "GenerationSnapshot",
    "EvolutionEvent",
    "EvolutionRunSummary",
    "EvolutionHistoryStore",
    "EvolutionHistory",
]
