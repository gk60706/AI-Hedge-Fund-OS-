"""Cross-process concurrency tests for ``ai_team.task_manager``."""

from __future__ import annotations

import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ai_team.task_manager import (
    TaskManager,
    TaskPriority,
    TaskType,
)


def _create_task_worker(storage_dir: str, index: int) -> str:
    manager = TaskManager(storage_dir=storage_dir)
    task = manager.create_task(
        title=f"Concurrent task {index}",
        description="Concurrency test",
        task_type=TaskType.STOCK_RESEARCH,
        priority=TaskPriority.NORMAL,
    )
    return task.task_id


def _submit_report_worker(
    storage_dir: str,
    task_id: str,
    agent_id: str,
) -> str:
    manager = TaskManager(storage_dir=storage_dir)
    task = manager.submit_agent_report(task_id, agent_id)
    return task.status


def test_concurrent_task_creation_has_valid_json(tmp_path: Path):
    ctx = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(max_workers=6, mp_context=ctx) as executor:
        task_ids = list(
            executor.map(
                _create_task_worker,
                [str(tmp_path)] * 12,
                range(12),
            )
        )

    assert len(task_ids) == 12
    assert len(set(task_ids)) == 12

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 12

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["task_id"] == path.stem
        assert data["status"] == "pending"


def test_concurrent_updates_same_task_are_serialized(tmp_path: Path):
    manager = TaskManager(storage_dir=tmp_path)

    task = manager.create_task(
        title="Concurrent report submission",
        description="Test concurrent updates",
        task_type=TaskType.STOCK_RESEARCH,
    )
    manager.assign_task(task.task_id)
    manager.start_task(task.task_id)

    agent_ids = ["chatgpt", "grok", "hark"]
    ctx = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(max_workers=3, mp_context=ctx) as executor:
        statuses = list(
            executor.map(
                _submit_report_worker,
                [str(tmp_path)] * 3,
                [task.task_id] * 3,
                agent_ids,
            )
        )

    # 每次提交只推进自己那一条 assignment，只有最后一次会把任务置为 submitted
    assert all(status in {"in_progress", "submitted"} for status in statuses)

    data = json.loads(
        (tmp_path / f"{task.task_id}.json").read_text(encoding="utf-8")
    )

    assert data["status"] == "submitted"
    assert set(data["assignments"]) == set(agent_ids)
    assert all(
        item["status"] == "submitted"
        for item in data["assignments"].values()
    )
    assert all(
        item["submitted_at"]
        for item in data["assignments"].values()
    )
