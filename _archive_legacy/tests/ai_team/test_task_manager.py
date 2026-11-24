
from pathlib import Path

import pytest

from ai_team.task_manager import (
    InvalidAgentError,
    InvalidTaskTransitionError,
    TaskManager,
    TaskNotFoundError,
    TaskPriority,
    TaskStatus,
    TaskType,
)


@pytest.fixture
def manager(tmp_path: Path):
    return TaskManager(storage_dir=tmp_path)


def create_sample_task(manager):
    return manager.create_task(
        title="天孚通信深度研究",
        description="研究公司基本面、行业趋势和估值。",
        task_type=TaskType.STOCK_RESEARCH,
        target="天孚通信 300394",
        priority=TaskPriority.HIGH,
        requirements=[
            "分析核心业务",
            "分析财务表现",
            "分析行业竞争",
        ],
        expected_outputs=[
            "研究报告",
            "风险分析",
            "投资结论",
        ],
    )


def test_create_task(manager):
    task = create_sample_task(manager)

    assert task.title == "天孚通信深度研究"
    assert task.status == TaskStatus.PENDING.value
    assert task.target == "天孚通信 300394"


def test_assign_three_agents(manager):
    task = create_sample_task(manager)

    assigned = manager.assign_task(task.task_id)

    assert len(assigned.assignments) == 3

    assert "chatgpt" in assigned.assignments
    assert "grok" in assigned.assignments
    assert "hark" in assigned.assignments

    assert assigned.status == TaskStatus.ASSIGNED.value


def test_agent_instructions_are_independent(manager):
    task = create_sample_task(manager)

    manager.assign_task(task.task_id)

    chatgpt_instruction = manager.get_agent_instruction(
        task.task_id,
        "chatgpt",
    )

    grok_instruction = manager.get_agent_instruction(
        task.task_id,
        "grok",
    )

    assert chatgpt_instruction != grok_instruction
    assert "Chief Investment Officer" in chatgpt_instruction
    assert "market intelligence" in grok_instruction


def test_invalid_agent(manager):
    task = create_sample_task(manager)

    with pytest.raises(InvalidAgentError):
        manager.assign_task(
            task.task_id,
            ["unknown_agent"],
        )


def test_start_task(manager):
    task = create_sample_task(manager)

    manager.assign_task(task.task_id)

    started = manager.start_task(task.task_id)

    assert started.status == TaskStatus.IN_PROGRESS.value


def test_submit_agent_reports(manager):
    task = create_sample_task(manager)

    manager.assign_task(task.task_id)
    manager.start_task(task.task_id)

    for agent_id in ["chatgpt", "grok", "hark"]:
        manager.submit_agent_report(
            task.task_id,
            agent_id,
        )

    assert (
        manager.get_task(task.task_id).status
        == TaskStatus.SUBMITTED.value
    )


def test_task_persistence(manager):
    task = create_sample_task(manager)

    task_id = task.task_id

    new_manager = TaskManager(
        storage_dir=manager.storage_dir
    )

    loaded_task = new_manager.get_task(task_id)

    assert loaded_task.title == task.title


def test_list_tasks(manager):
    create_sample_task(manager)

    tasks = manager.list_tasks()

    assert len(tasks) == 1


def test_task_not_found(manager):
    with pytest.raises(TaskNotFoundError):
        manager.get_task("UNKNOWN")


def test_invalid_transition(manager):
    task = create_sample_task(manager)

    with pytest.raises(InvalidTaskTransitionError):
        manager.update_status(
            task.task_id,
            TaskStatus.COMPLETED,
        )


def test_completion_ratio(manager):
    task = create_sample_task(manager)

    manager.assign_task(task.task_id)
    manager.start_task(task.task_id)

    manager.submit_agent_report(
        task.task_id,
        "chatgpt",
    )

    summary = manager.get_task_summary(task.task_id)

    assert summary["completion_ratio"] == pytest.approx(
        1 / 3
    )
