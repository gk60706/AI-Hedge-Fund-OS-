"""V3.9.3 断点续跑回归测试（checkpoint / restore / resume）。

从项目根运行：
    python -m pytest -q evolution/test_v393_checkpoint.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evolution.alpha_evolution import (
    AlphaEvolutionConfig,
    AlphaEvolutionEngine,
    CheckpointConsistencyError,
    CheckpointCorruptionError,
    CheckpointVersionError,
)
from evolution.evolution_history import (
    EvolutionHistory,
    EvolutionHistoryConfig,
)
from evolution.fitness import (
    AlphaFitnessConfig,
    FitnessResult,
)
from evolution.population import (
    AlphaPopulation,
    AlphaPopulationConfig,
)


class DeterministicFitnessEvaluator:
    """确定性测试用评估器：不读取任何行情数据。"""

    def __init__(self) -> None:
        self.config = AlphaFitnessConfig()

    def evaluate(
        self,
        genome,
        *,
        metrics=None,
        oos_metrics=None,
        apply_to_genome=True,
    ) -> FitnessResult:
        expression = genome.expression_string
        score = (sum(ord(char) for char in expression) % 1000) / 1000.0

        if apply_to_genome:
            genome.fitness = score

        return FitnessResult(
            genome_id=genome.genome_id,
            fitness=score,
            valid=True,
            component_scores={"test_score": score},
            weighted_score=score,
            accepted=False,
        )


def make_population() -> AlphaPopulation:
    population = AlphaPopulation(
        config=AlphaPopulationConfig(
            population_size=8,
            elite_size=2,
            seed=12345,
        )
    )
    population.initialize()
    return population


def make_research_evaluator():
    return lambda genome: {"metrics": {"ic": 0.03}, "oos_metrics": None}


def make_engine(history_path: Path, population=None) -> AlphaEvolutionEngine:
    history = EvolutionHistory(
        config=EvolutionHistoryConfig(
            output_path=str(history_path),
            enabled=True,
            flush_each_record=True,
            strict_loading=True,
        ),
        run_id="checkpoint-test-run",
    )

    return AlphaEvolutionEngine(
        population=population if population is not None else make_population(),
        research_evaluator=make_research_evaluator(),
        fitness_evaluator=DeterministicFitnessEvaluator(),
        config=AlphaEvolutionConfig(
            max_generations=4,
            patience=None,
            experiment_name="checkpoint_test",
            random_seed=12345,
        ),
        history=history,
    )


def test_checkpoint_resume_matches_uninterrupted_run(tmp_path: Path) -> None:
    reference_engine = make_engine(tmp_path / "reference.jsonl")
    reference_engine.run(max_generations=4)

    reference_best = reference_engine._best_fitness_seen
    reference_generation = reference_engine.population.generation
    reference_rng_draws = [
        reference_engine.population._rng.random() for _ in range(8)
    ]

    interrupted_engine = make_engine(tmp_path / "interrupted.jsonl")
    interrupted_engine.run(max_generations=2)

    checkpoint = tmp_path / "checkpoints" / "alpha.json"
    interrupted_engine.save_checkpoint(checkpoint)
    assert checkpoint.is_file()

    resumed_engine = AlphaEvolutionEngine.from_checkpoint(
        checkpoint,
        research_evaluator=make_research_evaluator(),
        fitness_evaluator=DeterministicFitnessEvaluator(),
        strict=True,
    )
    resumed_engine.run(max_generations=2)

    assert resumed_engine.population.generation == reference_generation
    assert resumed_engine._best_fitness_seen == pytest.approx(reference_best)

    resumed_rng_draws = [
        resumed_engine.population._rng.random() for _ in range(8)
    ]
    assert resumed_rng_draws == reference_rng_draws

    assert [
        report.generation for report in resumed_engine.generation_reports
    ] == [0, 1, 2, 3]


def test_checkpoint_state_is_json_safe_and_contains_rng(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "history.jsonl")
    engine.run(max_generations=1)

    state = engine.export_state()

    assert state["schema_version"] == "3.9.3"
    assert state["last_evaluated_generation"] == 0
    assert isinstance(state["rng_state"], list)
    assert state["history_run_id"] == "checkpoint-test-run"
    # NaN 会让下游 JSON 解析器静默接受非法数据，必须在这里就失败
    json.dumps(state, allow_nan=False)


def test_fitness_result_from_dict_roundtrip_and_validation() -> None:
    original = FitnessResult(
        genome_id="g-1",
        fitness=0.5,
        valid=True,
        component_scores={"ic": 0.03, "icir": None},
        weighted_score=0.4,
        penalties={"turnover": 0.1},
        penalty_total=0.1,
        missing_metrics=["hit_rate"],
        failed_checks=[],
        oos_available=False,
        oos_passed=None,
        accepted=False,
        details={"source": "test"},
    )

    restored = FitnessResult.from_dict(original.to_dict())
    assert restored == original

    with pytest.raises(ValueError, match="missing required fields"):
        FitnessResult.from_dict({"genome_id": "g-1"})

    with pytest.raises(ValueError, match="valid must be a bool"):
        FitnessResult.from_dict(
            {"genome_id": "g-1", "fitness": 0.5, "valid": "yes"}
        )

    with pytest.raises(ValueError, match="fitness must be a finite number"):
        FitnessResult.from_dict(
            {"genome_id": "g-1", "fitness": float("nan"), "valid": True}
        )


@pytest.mark.parametrize(
    "checkpoint_content",
    [
        "{invalid json",
        '{"schema_version":"3.9.3"}',
    ],
)
def test_corrupt_or_incomplete_checkpoint_raises(
    tmp_path: Path, checkpoint_content: str
) -> None:
    checkpoint = tmp_path / "broken.json"
    checkpoint.write_text(checkpoint_content, encoding="utf-8")

    with pytest.raises(CheckpointCorruptionError):
        AlphaEvolutionEngine.from_checkpoint(checkpoint)


def test_unsupported_schema_version_raises(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "history.jsonl")
    state = engine.export_state()
    state["schema_version"] = "99"

    checkpoint = tmp_path / "version_99.json"
    checkpoint.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(CheckpointVersionError):
        AlphaEvolutionEngine.from_checkpoint(checkpoint)


def test_history_generation_mismatch_strict_and_non_strict(
    tmp_path: Path,
) -> None:
    engine = make_engine(tmp_path / "history.jsonl")
    engine.run(max_generations=2)

    checkpoint = tmp_path / "mismatch.json"
    engine.save_checkpoint(checkpoint)

    state = json.loads(checkpoint.read_text(encoding="utf-8"))
    state["population"]["generation"] += 10
    checkpoint.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(CheckpointConsistencyError):
        AlphaEvolutionEngine.from_checkpoint(
            checkpoint,
            research_evaluator=make_research_evaluator(),
            fitness_evaluator=DeterministicFitnessEvaluator(),
            strict=True,
        )

    resumed = AlphaEvolutionEngine.from_checkpoint(
        checkpoint,
        research_evaluator=make_research_evaluator(),
        fitness_evaluator=DeterministicFitnessEvaluator(),
        strict=False,
    )

    assert "checkpoint_history_mismatch" in resumed.run_metadata
    assert resumed.population.generation == state["population"]["generation"]
