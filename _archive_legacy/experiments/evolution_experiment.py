"""
AI Hedge Fund OS - V3.9.3
File: experiments/evolution_experiment.py
Purpose
-------
Run and record reproducible Alpha Evolution experiments.
Features
--------
1. Wraps the AlphaEvolutionEngine without replacing its implementation.
2. Records experiment configuration, generation reports, best Alpha,
   training/OOS metrics, runtime, stop reason, and errors.
3. Appends records to JSONL for auditability.
4. Supports an optional registry_writer callback for integration with
   the project's existing experiments/registry.py.
5. Uses Python 3.11+.
6. Does not read API keys or expose live-trading interfaces.
Example
-------
from experiments.evolution_experiment import (
    AlphaEvolutionExperiment,
    EvolutionExperimentConfig,
)
experiment = AlphaEvolutionExperiment(
    evolution_engine=evolution_engine,
    config=EvolutionExperimentConfig(
        experiment_name="alpha_evolution_v393",
        max_generations=20,
        output_path="experiments/runs/alpha_evolution.jsonl",
    ),
)
result = experiment.run()
print(result.status)
print(result.record_path)
"""
from __future__ import annotations
import dataclasses
import hashlib
import json
import logging
import math
import os
import platform
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence
logger = logging.getLogger(__name__)
JSONMapping = Mapping[str, Any]
RegistryWriter = Callable[[dict[str, Any]], Any]
class EvolutionExperimentError(RuntimeError):
    """Base exception for Alpha Evolution experiment errors."""
class ExperimentSerializationError(EvolutionExperimentError):
    """Raised when an experiment record cannot be serialized."""
@dataclass(frozen=True, slots=True)
class EvolutionExperimentConfig:
    """Configuration for a single Alpha Evolution experiment."""
    experiment_name: str = "alpha_evolution_v393"
    max_generations: Optional[int] = 20
    # JSONL record storage. Set to None to disable local JSONL output.
    output_path: Optional[str] = (
        "experiments/runs/evolution_experiments.jsonl"
    )
    # If True, exceptions are recorded and returned instead of re-raised.
    capture_exceptions: bool = True
    # Optional metadata describing the data, universe, and research setup.
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    universe: Optional[str] = None
    strategy_version: str = "V3.9.3"
    # User-supplied reproducibility information.
    random_seed: Optional[int] = None
    code_version: Optional[str] = None
    search_space: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    # A unique ID is generated for each run unless explicitly supplied.
    experiment_id: Optional[str] = None
    def __post_init__(self) -> None:
        if not self.experiment_name.strip():
            raise ValueError("experiment_name must not be empty")
        if self.max_generations is not None and self.max_generations < 1:
            raise ValueError("max_generations must be >= 1 or None")
        if self.random_seed is not None and self.random_seed < 0:
            raise ValueError("random_seed must be >= 0 or None")
@dataclass(slots=True)
class EvolutionExperimentResult:
    """Public result returned by AlphaEvolutionExperiment.run()."""
    experiment_id: str
    experiment_name: str
    status: str
    started_at: str
    finished_at: str
    duration_seconds: float
    record_path: Optional[str] = None
    generations_completed: int = 0
    best_genome_id: Optional[str] = None
    best_expression: Optional[str] = None
    best_fitness: Optional[float] = None
    best_metrics: dict[str, Any] = field(default_factory=dict)
    stop_reason: Optional[str] = None
    generation_reports: list[dict[str, Any]] = field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return _json_safe(dataclasses.asdict(self))
class JsonlExperimentStore:
    """
    Append-only JSONL experiment store.
    Each successful append writes one complete JSON object followed by a
    newline. A process-local lock prevents concurrent threads from
    interleaving writes through this store instance.
    For multi-process or distributed workers, use a database or a registry
    with transactional writes instead.
    """
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
    def append(self, record: JSONMapping) -> str:
        """Append one record and return the absolute file path."""
        safe_record = _json_safe(dict(record))
        try:
            serialized = json.dumps(
                safe_record,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ExperimentSerializationError(
                f"Experiment record is not JSON serializable: {exc}"
            ) from exc
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(serialized)
                file.write("\n")
                file.flush()
        return str(self.path.resolve())
class AlphaEvolutionExperiment:
    """
    Experiment wrapper for evolution.alpha_evolution.AlphaEvolutionEngine.
    The engine is injected rather than imported or constructed here. This
    keeps this module decoupled from the exact population implementation.
    """
    def __init__(
        self,
        evolution_engine: Any,
        config: Optional[EvolutionExperimentConfig] = None,
        registry_writer: Optional[RegistryWriter] = None,
    ) -> None:
        if evolution_engine is None:
            raise ValueError("evolution_engine must not be None")
        self.evolution_engine = evolution_engine
        self.config = config or EvolutionExperimentConfig()
        self.registry_writer = registry_writer
        self.experiment_id = (
            self.config.experiment_id or str(uuid.uuid4())
        )
        self.store = (
            JsonlExperimentStore(self.config.output_path)
            if self.config.output_path
            else None
        )
    def run(self) -> EvolutionExperimentResult:
        """
        Execute one experiment and persist its final record.
        If capture_exceptions=True, runtime errors are recorded and returned
        as a result with status="failed". Otherwise, the error is recorded
        when possible and then re-raised.
        """
        started_epoch = time.perf_counter()
        started_at = _utc_now()
        status = "completed"
        error_type: Optional[str] = None
        error_message: Optional[str] = None
        traceback_text: Optional[str] = None
        engine_result: Any = None
        logger.info(
            "Starting Alpha Evolution experiment: %s (%s)",
            self.config.experiment_name,
            self.experiment_id,
        )
        try:
            engine_result = self._run_engine()
        except Exception as exc:
            status = "failed"
            error_type = type(exc).__name__
            error_message = str(exc)
            traceback_text = traceback.format_exc()
            logger.exception(
                "Alpha Evolution experiment failed: %s",
                self.experiment_id,
            )
            if not self.config.capture_exceptions:
                # Persist the failure record before propagating the error.
                result = self._build_result(
                    engine_result=None,
                    status=status,
                    started_at=started_at,
                    started_epoch=started_epoch,
                    error_type=error_type,
                    error_message=error_message,
                )
                self._persist(result, traceback_text=traceback_text)
                raise
        result = self._build_result(
            engine_result=engine_result,
            status=status,
            started_at=started_at,
            started_epoch=started_epoch,
            error_type=error_type,
            error_message=error_message,
        )
        try:
            self._persist(result, traceback_text=traceback_text)
        except Exception as persist_exc:
            logger.exception(
                "Failed to persist experiment record: %s",
                self.experiment_id,
            )
            if not self.config.capture_exceptions:
                raise
            result.status = "persistence_failed"
            result.error_type = type(persist_exc).__name__
            result.error_message = str(persist_exc)
        logger.info(
            "Finished Alpha Evolution experiment %s with status=%s",
            self.experiment_id,
            result.status,
        )
        return result
    def _run_engine(self) -> Any:
        """Call the injected evolution engine."""
        run_method = getattr(self.evolution_engine, "run", None)
        if not callable(run_method):
            raise EvolutionExperimentError(
                "evolution_engine must expose a callable run() method"
            )
        # AlphaEvolutionEngine from V3.9.3 accepts max_generations.
        # Fall back to a no-argument call for compatible external engines.
        try:
            return run_method(max_generations=self.config.max_generations)
        except TypeError as exc:
            # Only retry when the signature rejects this keyword.
            # Do not silently retry arbitrary TypeErrors raised inside run().
            if _unexpected_keyword_error(exc, "max_generations"):
                return run_method()
            raise
    def _build_result(
        self,
        engine_result: Any,
        status: str,
        started_at: str,
        started_epoch: float,
        error_type: Optional[str],
        error_message: Optional[str],
    ) -> EvolutionExperimentResult:
        """Build the public result from engine output and its current state."""
        finished_at = _utc_now()
        duration = max(0.0, time.perf_counter() - started_epoch)
        reports = _extract_generation_reports(engine_result)
        if not reports:
            reports = _extract_generation_reports(self.evolution_engine)
        best_genome = _extract_best_genome(
            engine_result,
            self.evolution_engine,
        )
        best_id, best_expression, best_fitness, best_metrics = (
            _extract_genome_summary(best_genome)
        )
        generations_completed = _extract_generations_completed(
            engine_result,
            reports,
            self.evolution_engine,
        )
        stop_reason = _extract_stop_reason(engine_result)
        return EvolutionExperimentResult(
            experiment_id=self.experiment_id,
            experiment_name=self.config.experiment_name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(duration, 6),
            record_path=None,
            generations_completed=generations_completed,
            best_genome_id=best_id,
            best_expression=best_expression,
            best_fitness=best_fitness,
            best_metrics=best_metrics,
            stop_reason=stop_reason,
            generation_reports=reports,
            error_type=error_type,
            error_message=error_message,
        )
    def _persist(
        self,
        result: EvolutionExperimentResult,
        traceback_text: Optional[str] = None,
    ) -> None:
        """Persist the experiment record to JSONL and/or an external registry."""
        record = {
            "schema_version": "1.0",
            "experiment": {
                "experiment_id": self.experiment_id,
                "experiment_name": self.config.experiment_name,
                "strategy_version": self.config.strategy_version,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "duration_seconds": result.duration_seconds,
                "status": result.status,
            },
            "environment": {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "code_version": self.config.code_version,
            },
            "data": {
                "data_start": self.config.data_start,
                "data_end": self.config.data_end,
                "universe": self.config.universe,
            },
            "reproducibility": {
                "random_seed": self.config.random_seed,
                "search_space": self.config.search_space,
            },
            "configuration": _public_config_dict(self.config),
            "result": result.to_dict(),
            "metadata": self.config.metadata,
            "error": {
                "type": result.error_type,
                "message": result.error_message,
                "traceback": traceback_text,
            } if result.error_type else None,
            "record_hash": None,
        }
        # Hash the canonical record without the hash field itself.
        record["record_hash"] = _stable_hash(record)
        if self.store is not None:
            result.record_path = self.store.append(record)
            record["result"]["record_path"] = result.record_path
        if self.registry_writer is not None:
            # Give the callback its own object so it cannot mutate our record.
            self.registry_writer(_json_safe(record))
def _extract_generation_reports(source: Any) -> list[dict[str, Any]]:
    """Extract generation reports from an engine result or engine instance."""
    if source is None:
        return []
    raw = _get_value(source, "generation_reports")
    if raw is None:
        raw = _get_value(source, "reports")
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        raw = list(raw.values())
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    reports: list[dict[str, Any]] = []
    for item in raw:
        converted = _object_to_dict(item)
        if converted:
            reports.append(_json_safe(converted))
    return reports
def _extract_best_genome(engine_result: Any, engine: Any) -> Any:
    """Find the best genome without requiring one fixed result schema."""
    for source in (engine_result, engine):
        if source is None:
            continue
        for name in ("best_genome", "best_alpha", "best_individual"):
            candidate = _get_value(source, name)
            if candidate is not None:
                return candidate
    # Compatibility fallback for the V3.9.3 engine described in this project.
    best_method = getattr(engine, "_best_genome", None)
    if callable(best_method):
        try:
            return best_method()
        except Exception:
            logger.debug("Could not retrieve best genome", exc_info=True)
    population = _get_value(engine, "population")
    if population is not None:
        candidates = list(_safe_iter(population))
        if candidates:
            candidates.sort(
                key=lambda genome: _as_float(
                    _get_value(genome, "fitness"),
                    default=float("-inf"),
                ),
                reverse=True,
            )
            return candidates[0]
    return None
def _extract_genome_summary(
    genome: Any,
) -> tuple[Optional[str], Optional[str], Optional[float], dict[str, Any]]:
    if genome is None:
        return None, None, None, {}
    genome_id = _get_value(genome, "genome_id")
    if genome_id is None:
        genome_id = _get_value(genome, "alpha_id")
    expression = _get_value(genome, "expression")
    if expression is not None:
        expression_text = getattr(expression, "to_string", None)
        if callable(expression_text):
            try:
                expression_text = expression_text()
            except Exception:
                expression_text = None
        if not isinstance(expression_text, str):
            expression_text = str(expression)
    else:
        expression_text = None
    fitness = _as_optional_float(_get_value(genome, "fitness"))
    metric_names = (
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
    )
    metrics: dict[str, Any] = {}
    for name in metric_names:
        value = _get_value(genome, name)
        if value is not None:
            metrics[name] = _json_safe(value)
    metadata = _get_value(genome, "metadata")
    if isinstance(metadata, Mapping):
        for key in ("fitness_result", "oos_metrics", "evaluation_status"):
            if key in metadata:
                metrics[key] = _json_safe(metadata[key])
    return (
        str(genome_id) if genome_id is not None else None,
        expression_text,
        fitness,
        metrics,
    )
def _extract_generations_completed(
    engine_result: Any,
    reports: list[dict[str, Any]],
    engine: Any,
) -> int:
    for source in (engine_result, engine):
        for key in ("generations_completed", "completed_generations"):
            value = _get_value(source, key)
            if isinstance(value, int) and value >= 0:
                return value
    if reports:
        return len(reports)
    population = _get_value(engine, "population")
    generation = _get_value(population, "generation")
    if isinstance(generation, int) and generation >= 0:
        return generation + 1
    return 0
def _extract_stop_reason(engine_result: Any) -> Optional[str]:
    for key in ("stop_reason", "stopped_reason", "termination_reason"):
        value = _get_value(engine_result, key)
        if value is not None:
            return str(value)
    return None
def _get_value(source: Any, name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(name)
    return getattr(source, name, None)
def _object_to_dict(value: Any) -> dict[str, Any]:
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
            converted = to_dict()
            if isinstance(converted, Mapping):
                return dict(converted)
        except Exception:
            logger.debug("to_dict() failed for %r", value, exc_info=True)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {"value": str(value)}
def _safe_iter(value: Any) -> list[Any]:
    try:
        return list(iter(value))
    except (TypeError, RuntimeError):
        return []
def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        converted = float(value)
        return converted if math.isfinite(converted) else default
    except (TypeError, ValueError):
        return default
def _as_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        converted = float(value)
        return converted if math.isfinite(converted) else None
    except (TypeError, ValueError):
        return None
def _json_safe(value: Any) -> Any:
    """Recursively convert supported Python objects to strict JSON values."""
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
    # NumPy scalar support without making NumPy a mandatory dependency.
    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return _json_safe(item_method())
        except Exception:
            pass
    # Pandas Timestamp and similar date-like values.
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            pass
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    return str(value)
def _public_config_dict(config: EvolutionExperimentConfig) -> dict[str, Any]:
    """Return public config values; do not serialize arbitrary environment data."""
    return _json_safe(dataclasses.asdict(config))
def _stable_hash(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _json_safe(dict(value)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
def _unexpected_keyword_error(exc: TypeError, keyword: str) -> bool:
    message = str(exc).lower()
    return (
        "unexpected keyword" in message
        and keyword.lower() in message
    ) or (
        "invalid keyword" in message
        and keyword.lower() in message
    )
__all__ = [
    "EvolutionExperimentError",
    "ExperimentSerializationError",
    "EvolutionExperimentConfig",
    "EvolutionExperimentResult",
    "JsonlExperimentStore",
    "AlphaEvolutionExperiment",
]
