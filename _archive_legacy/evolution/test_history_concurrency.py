"""P3 并发回归：跨进程写同一 JSONL 历史 / 同一 checkpoint。

从项目根运行：
    python -m pytest -q evolution/test_history_concurrency.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evolution.alpha_evolution import (
    AlphaEvolutionConfig,
    AlphaEvolutionEngine,
)
from evolution.evolution_history import (
    EvolutionHistoryStore,
    EvolutionHistoryLockError,
)
from evolution.file_lock import FileLock
from evolution.population import AlphaPopulation, AlphaPopulationConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]

APPEND_WORKER = r'''
import sys
from evolution.evolution_history import EvolutionHistoryStore

path = sys.argv[1]
count = int(sys.argv[2])
tag = sys.argv[3]
timeout = float(sys.argv[4])

store = EvolutionHistoryStore(
    path,
    flush_each_record=True,
    lock_timeout=timeout,
)
for index in range(count):
    store.append(
        {
            "run_id": tag,
            "record_type": "generation",
            "generation": index,
            "payload": {"tag": tag, "index": index},
            "record_hash": f"{tag}-{index}",
        }
    )
print("APPENDED", count)
'''

CHECKPOINT_WORKER = r'''
import sys
from pathlib import Path

from evolution.alpha_evolution import AlphaEvolutionConfig, AlphaEvolutionEngine
from evolution.population import AlphaPopulation, AlphaPopulationConfig

path = Path(sys.argv[1])
worker = sys.argv[2]

population = AlphaPopulation(
    config=AlphaPopulationConfig(population_size=6, elite_size=1, seed=12345)
)
population.initialize()
engine = AlphaEvolutionEngine(
    population=population,
    research_evaluator=lambda genome: {"metrics": {"ic": 0.01}},
    config=AlphaEvolutionConfig(
        max_generations=1, patience=None, experiment_name="concurrency"
    ),
)
for attempt in range(3):
    engine.run_metadata["worker"] = f"{worker}-{attempt}"
    engine.save_checkpoint(path)
print("SAVED", worker)
'''


def _run_worker(script_text: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    script = cwd / f"worker_{abs(hash(tuple(args))) % 10_000}.py"
    script.write_text(script_text, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )


def test_multiprocess_append_keeps_every_record(tmp_path: Path) -> None:
    history = tmp_path / "concurrent.jsonl"
    processes = 4
    per_process = 25

    completed = []
    for index in range(processes):
        completed.append(
            _run_worker(
                APPEND_WORKER,
                [str(history), str(per_process), f"tag-{index}", "10"],
                tmp_path,
            )
        )

    for result in completed:
        assert result.returncode == 0, result.stderr

    lines = [
        line
        for line in history.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == processes * per_process

    records = [json.loads(line) for line in lines]
    for index in range(processes):
        tag = f"tag-{index}"
        indices = sorted(
            record["payload"]["index"]
            for record in records
            if record["run_id"] == tag
        )
        assert indices == list(range(per_process))


def test_append_times_out_when_lock_is_held(tmp_path: Path) -> None:
    history = tmp_path / "locked.jsonl"
    history.write_text("", encoding="utf-8")

    with FileLock(history, timeout=5):
        result = _run_worker(
            APPEND_WORKER,
            [str(history), "1", "blocked", "0.3"],
            tmp_path,
        )

    assert result.returncode != 0
    assert "EvolutionHistoryLockError" in (result.stderr or "")


def test_concurrent_checkpoint_saves_leave_valid_file(tmp_path: Path) -> None:
    checkpoint = tmp_path / "alpha.json"
    completed = [
        _run_worker(CHECKPOINT_WORKER, [str(checkpoint), f"w{index}"], tmp_path)
        for index in range(4)
    ]

    for result in completed:
        assert result.returncode == 0, result.stderr

    state = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert state["schema_version"] == "3.9.3"
    assert isinstance(state["population"]["generation"], int)
    assert isinstance(state["rng_state"], list)

    # 同一目录不应残留半成品临时文件
    leftovers = list(tmp_path.glob(".alpha.json.*.tmp"))
    assert leftovers == []


def test_lock_timeout_raises_history_lock_error(tmp_path: Path) -> None:
    history = tmp_path / "guarded.jsonl"
    store = EvolutionHistoryStore(history, lock_timeout=0.2)

    with FileLock(history, timeout=5):
        with pytest.raises(EvolutionHistoryLockError):
            store.append({"run_id": "x", "record_type": "generation"})
