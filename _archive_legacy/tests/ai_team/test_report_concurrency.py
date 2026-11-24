"""Multiprocess concurrency tests for ReportCollector."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from ai_team.report_collector import (
    DuplicateReportError,
    ReportCollector,
)
from ai_team.task_manager import TaskManager


AGENTS = ("chatgpt", "grok", "hark")


REPORT_CONTENT = """
# Executive Summary

This report evaluates the target company's business fundamentals,
industry position, competitive advantages and investment risks.
The analysis considers operating performance, financial quality
and the sustainability of future growth.

# Key Findings

The company has identifiable competitive advantages.
Its core business has established customer relationships.
Revenue growth and profitability require continued monitoring.

# Evidence and Sources

The analysis should be supported by company announcements,
financial statements, industry data and publicly available
market information.

# Analytical Framework

The evaluation considers valuation, profitability, cash flow,
balance sheet quality, industry trends and competitive positioning.

# Risk Assessment

Potential risks include industry competition, demand fluctuations,
margin pressure, execution risks and valuation contraction.

# Investment Conclusion

Investment decisions should consider valuation, business quality,
risk exposure and the expected investment horizon.
"""


def _create_task(storage_dir: Path) -> str:
    """Create an assigned, in-progress task and return its ID."""

    manager = TaskManager(
        storage_dir=storage_dir,
    )

    task = manager.create_task(
        title="Report concurrency test",
        description="Multiprocess report collection test",
        task_type="stock_research",
        created_by="pytest",
    )

    manager.assign_task(
        task.task_id,
        agent_ids=list(AGENTS),
    )

    manager.start_task(task.task_id)

    return task.task_id


def _report_worker(
    task_storage: str,
    report_storage: str,
    task_id: str,
    agent_id: str,
    start_event,
    result_queue,
) -> None:
    """
    Module-level worker required by Windows spawn.

    Each process creates its own TaskManager and ReportCollector.
    """

    try:

        manager = TaskManager(
            storage_dir=Path(task_storage),
        )

        collector = ReportCollector(
            task_manager=manager,
            storage_dir=Path(report_storage),
        )

        start_event.wait(timeout=30)

        record = collector.collect_report(
            task_id=task_id,
            agent_id=agent_id,
            content=REPORT_CONTENT,
            title=f"{agent_id} concurrency report",
            source="concurrency_test",
        )

        result_queue.put(
            ("success", agent_id, record.report_id)
        )

    except DuplicateReportError:

        result_queue.put(
            ("duplicate", agent_id, None)
        )

    except Exception as exc:

        result_queue.put(
            (
                "error",
                agent_id,
                f"{type(exc).__name__}: {exc}",
            )
        )


def _run_workers(
    tmp_path: Path,
    agents: tuple[str, ...],
) -> tuple[str, list[tuple]]:
    """Create the task, run one process per agent, collect the results."""

    context = multiprocessing.get_context("spawn")

    task_storage = tmp_path / "tasks"
    report_storage = tmp_path / "reports"

    task_storage.mkdir(parents=True, exist_ok=True)
    report_storage.mkdir(parents=True, exist_ok=True)

    task_id = _create_task(task_storage)

    start_event = context.Event()
    result_queue = context.Queue()

    processes = []

    for agent_id in agents:

        process = context.Process(
            target=_report_worker,
            args=(
                str(task_storage),
                str(report_storage),
                task_id,
                agent_id,
                start_event,
                result_queue,
            ),
        )

        process.start()
        processes.append(process)

    # Release all workers together.
    start_event.set()

    for process in processes:
        process.join(timeout=45)

    alive = [
        process.pid
        for process in processes
        if process.is_alive()
    ]

    for process in processes:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)

    assert not alive, f"Worker processes did not finish: {alive}"

    assert all(
        process.exitcode == 0
        for process in processes
    ), [
        (process.pid, process.exitcode)
        for process in processes
    ]

    results = []

    for _ in processes:
        results.append(result_queue.get(timeout=10))

    result_queue.close()
    result_queue.join_thread()

    return task_id, results


def _load_and_validate_reports(
    report_storage: Path,
    task_id: str,
    expected_count: int,
) -> list[dict]:
    """Verify metadata JSON and the corresponding Markdown files."""

    metadata_dir = report_storage / "_metadata"

    metadata_files = list(metadata_dir.glob("*.json"))

    assert len(metadata_files) == expected_count

    records = []

    for metadata_file in metadata_files:

        with metadata_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        assert data["task_id"] == task_id
        assert data["agent_id"] in AGENTS

        report_path = Path(data["report_path"])

        assert report_path.exists()
        assert report_path.is_file()
        assert report_path.suffix == ".md"

        assert report_path.read_text(encoding="utf-8").strip()

        records.append(data)

    return records


def test_same_task_same_agent_only_one_process_succeeds(
    tmp_path: Path,
) -> None:
    """Three processes submitting the same agent report."""

    task_id, results = _run_workers(
        tmp_path=tmp_path,
        agents=("chatgpt", "chatgpt", "chatgpt"),
    )

    successes = [r for r in results if r[0] == "success"]
    duplicates = [r for r in results if r[0] == "duplicate"]
    errors = [r for r in results if r[0] == "error"]

    assert len(successes) == 1, results
    assert len(duplicates) == 2, results
    assert errors == []

    report_ids = {r[2] for r in successes}

    assert len(report_ids) == 1

    records = _load_and_validate_reports(
        tmp_path / "reports",
        task_id,
        expected_count=1,
    )

    assert records[0]["agent_id"] == "chatgpt"


def test_different_agents_can_submit_concurrently(
    tmp_path: Path,
) -> None:
    """Three different agents should all succeed."""

    task_id, results = _run_workers(
        tmp_path=tmp_path,
        agents=AGENTS,
    )

    successes = [r for r in results if r[0] == "success"]
    duplicates = [r for r in results if r[0] == "duplicate"]
    errors = [r for r in results if r[0] == "error"]

    assert len(successes) == 3, results
    assert len(duplicates) == 0, results
    assert errors == []

    assert {r[1] for r in successes} == set(AGENTS)

    records = _load_and_validate_reports(
        tmp_path / "reports",
        task_id,
        expected_count=3,
    )

    assert {record["agent_id"] for record in records} == set(AGENTS)

    report_ids = {record["report_id"] for record in records}

    assert len(report_ids) == 3
