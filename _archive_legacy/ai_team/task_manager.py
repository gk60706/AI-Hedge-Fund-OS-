
"""
AI Hedge Fund OS V3.10
Multi-AI Collaboration Engine

Step 2: Task Manager

Features:
- Create research tasks
- Assign tasks to AI agents
- Generate independent agent instructions
- Track task status
- Persist tasks as JSON
- Query task history
- Cancel and reassign tasks

Python >= 3.11
No API required.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from evolution.file_lock import FileLock

from ai_team.config import (
    AgentConfig,
    AgentRole,
    CollaborationMode,
    ProjectMode,
    TeamConfig,
    get_default_config,
)


logger = logging.getLogger(__name__)


# ============================================================
# Exceptions
# ============================================================

class TaskManagerError(Exception):
    """Base task manager exception."""


class TaskNotFoundError(TaskManagerError):
    """Raised when a task does not exist."""


class InvalidTaskTransitionError(TaskManagerError):
    """Raised when an invalid status transition is requested."""


class InvalidAgentError(TaskManagerError):
    """Raised when an unknown agent is requested."""


class TaskPersistenceError(TaskManagerError):
    """Raised when task persistence fails."""


# ============================================================
# Enums
# ============================================================

class TaskType(str, Enum):
    STOCK_RESEARCH = "stock_research"
    INDUSTRY_RESEARCH = "industry_research"
    MARKET_ANALYSIS = "market_analysis"
    FINANCIAL_ANALYSIS = "financial_analysis"
    BUSINESS_RESEARCH = "business_research"
    SOFTWARE_DEVELOPMENT = "software_development"
    GENERAL_RESEARCH = "general_research"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# Task data models
# ============================================================

@dataclass
class AgentAssignment:
    agent_id: str
    agent_name: str
    role: str
    instruction: str
    status: str = "assigned"
    assigned_at: str = ""
    submitted_at: str | None = None
    report_path: str | None = None


@dataclass
class ResearchTask:
    task_id: str
    title: str
    description: str
    task_type: str
    project_mode: str
    priority: str

    status: str = TaskStatus.PENDING.value

    target: str | None = None
    deadline: str | None = None

    requirements: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)

    assignments: dict[str, AgentAssignment] = field(
        default_factory=dict
    )

    created_at: str = ""
    updated_at: str = ""

    created_by: str = "user"

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResearchTask:
        assignments = {
            agent_id: AgentAssignment(**assignment)
            for agent_id, assignment
            in data.get("assignments", {}).items()
        }

        payload = dict(data)
        payload["assignments"] = assignments

        return cls(**payload)


# ============================================================
# Task manager
# ============================================================

class TaskManager:
    """
    Central task manager for the multi-AI team.

    The manager does not call AI APIs.

    In free mode, users manually transfer generated
    instructions between ChatGPT, Grok and Hark.
    """

    VALID_TRANSITIONS = {
        TaskStatus.PENDING: {
            TaskStatus.ASSIGNED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.ASSIGNED: {
            TaskStatus.IN_PROGRESS,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.IN_PROGRESS: {
            TaskStatus.SUBMITTED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        },
        TaskStatus.SUBMITTED: {
            TaskStatus.COMPLETED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.FAILED,
        },
        TaskStatus.COMPLETED: set(),
        TaskStatus.FAILED: {
            TaskStatus.PENDING,
            TaskStatus.CANCELLED,
        },
        TaskStatus.CANCELLED: set(),
    }

    def __init__(
        self,
        config: TeamConfig | None = None,
        storage_dir: Path | str | None = None,
    ) -> None:

        self.config = config or get_default_config()

        self.storage_dir = (
            Path(storage_dir)
            if storage_dir is not None
            else self.config.tasks_dir
        )

        self.storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._tasks: dict[str, ResearchTask] = {}

        self._load_tasks()

    # --------------------------------------------------------
    # Utility
    # --------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _validate_text(
        value: str,
        field_name: str,
    ) -> str:

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return value.strip()

    @staticmethod
    def _validate_enum(
        value: Enum | str,
        enum_class: type[Enum],
        field_name: str,
    ) -> str:

        try:
            return enum_class(value).value
        except ValueError as exc:
            raise ValueError(
                f"Invalid {field_name}: {value}"
            ) from exc

    @staticmethod
    def _safe_task_id(task_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", task_id):
            raise ValueError("Invalid task ID.")

        return task_id

    def _task_path(self, task_id: str) -> Path:
        safe_id = self._safe_task_id(task_id)
        return self.storage_dir / f"{safe_id}.json"

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def _save_task_unlocked(self, task: ResearchTask) -> None:
        """调用方必须已经持有该任务的 FileLock。"""

        path = self._task_path(task.task_id)

        temp_path = path.with_name(
            f"{path.stem}.{uuid.uuid4().hex}.tmp"
        )

        try:

            with temp_path.open("x", encoding="utf-8") as file:

                json.dump(
                    task.to_dict(),
                    file,
                    ensure_ascii=False,
                    indent=4,
                )

                file.flush()

            temp_path.replace(path)

        except (OSError, TypeError, ValueError) as exc:

            temp_path.unlink(missing_ok=True)

            raise TaskPersistenceError(
                f"Unable to save task {task.task_id}"
            ) from exc

    def _save_task(self, task: ResearchTask) -> None:
        """独立保存入口：加锁后原子替换。"""

        path = self._task_path(task.task_id)

        with FileLock(path):

            self._save_task_unlocked(task)

    @contextmanager
    def _edit_task(self, task_id: str) -> Iterator[ResearchTask]:
        """跨进程串行化一次完整的读取-修改-写回事务。"""

        path = self._task_path(task_id)

        with FileLock(path):

            try:

                with path.open("r", encoding="utf-8") as file:

                    task = ResearchTask.from_dict(json.load(file))

            except FileNotFoundError as exc:

                raise TaskNotFoundError(task_id) from exc

            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:

                raise TaskPersistenceError(
                    f"Unable to load task {task_id}"
                ) from exc

            yield task

            self._save_task_unlocked(task)

            self._tasks[task_id] = task

    def _load_tasks(self) -> None:

        for path in self.storage_dir.glob("*.json"):

            try:
                with path.open(
                    "r",
                    encoding="utf-8",
                ) as file:

                    data = json.load(file)

                task = ResearchTask.from_dict(data)

                if path.stem != task.task_id:
                    raise ValueError(
                        "Task filename and ID mismatch."
                    )

                self._tasks[task.task_id] = task

            except (
                OSError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
                KeyError,
            ) as exc:

                logger.error(
                    "Unable to load task file %s: %s",
                    path,
                    exc,
                )

    # --------------------------------------------------------
    # Task creation
    # --------------------------------------------------------

    def create_task(
        self,
        title: str,
        description: str,
        task_type: TaskType | str,
        project_mode: ProjectMode | str | None = None,
        priority: TaskPriority | str = TaskPriority.NORMAL,
        target: str | None = None,
        deadline: str | None = None,
        requirements: list[str] | None = None,
        expected_outputs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: str = "user",
    ) -> ResearchTask:

        title = self._validate_text(title, "title")

        description = self._validate_text(
            description,
            "description",
        )

        task_type_value = self._validate_enum(
            task_type,
            TaskType,
            "task_type",
        )

        priority_value = self._validate_enum(
            priority,
            TaskPriority,
            "priority",
        )

        if project_mode is None:
            project_mode_value = self.config.project_mode.value
        else:
            project_mode_value = self._validate_enum(
                project_mode,
                ProjectMode,
                "project_mode",
            )

        if target is not None:
            target = self._validate_text(target, "target")

        if deadline is not None:
            deadline = self._validate_text(
                deadline,
                "deadline",
            )

        task_id = (
            "TASK-"
            + datetime.now(timezone.utc).strftime("%Y%m%d")
            + "-"
            + uuid.uuid4().hex[:8].upper()
        )

        now = self._now()

        task = ResearchTask(
            task_id=task_id,
            title=title,
            description=description,
            task_type=task_type_value,
            project_mode=project_mode_value,
            priority=priority_value,
            target=target,
            deadline=deadline,
            requirements=requirements or [],
            expected_outputs=expected_outputs or [],
            created_at=now,
            updated_at=now,
            created_by=created_by,
            metadata=metadata or {},
        )

        self._tasks[task_id] = task

        try:
            self._save_task(task)
        except TaskPersistenceError:
            del self._tasks[task_id]
            raise

        return task

    # --------------------------------------------------------
    # Agent instruction generation
    # --------------------------------------------------------

    def _build_agent_instruction(
        self,
        task: ResearchTask,
        agent: AgentConfig,
    ) -> str:

        requirements = "\n".join(
            f"- {item}"
            for item in task.requirements
        ) or "- Follow the task description."

        outputs = "\n".join(
            f"- {item}"
            for item in task.expected_outputs
        ) or "- Provide a structured research report."

        role_guidance = {
            AgentRole.CIO: (
                "Act as the Chief Investment Officer. "
                "Define the analytical framework, identify "
                "decision criteria and evaluate evidence."
            ),
            AgentRole.INTELLIGENCE: (
                "Act as the independent market intelligence "
                "officer. Focus on external information, "
                "recent developments, sentiment and "
                "counter-evidence."
            ),
            AgentRole.ANALYST: (
                "Act as an independent research analyst. "
                "Focus on primary evidence, detailed analysis, "
                "assumptions and logical consistency."
            ),
        }

        return f"""
AI HEDGE FUND OS - MULTI-AI RESEARCH TASK

Task ID: {task.task_id}

Agent: {agent.name}
Platform: {agent.platform}
Role: {agent.role.value}

TASK TITLE:
{task.title}

TASK DESCRIPTION:
{task.description}

RESEARCH TARGET:
{task.target or "Not specified"}

TASK TYPE:
{task.task_type}

PROJECT MODE:
{task.project_mode}

PRIORITY:
{task.priority}

YOUR ROLE:
{role_guidance[agent.role]}

RESPONSIBILITIES:
{chr(10).join("- " + item for item in agent.responsibilities)}

REQUIREMENTS:
{requirements}

EXPECTED OUTPUTS:
{outputs}

IMPORTANT RULES:
1. Conduct independent analysis.
2. Do not assume other AI conclusions are correct.
3. Separate verified facts from assumptions.
4. Identify missing information.
5. Provide source names and source dates when available.
6. Never invent financial data or market prices.
7. Clearly explain uncertainty.
8. Do not execute financial transactions.

REPORT FORMAT:
1. Executive Summary
2. Key Findings
3. Evidence and Sources
4. Analytical Reasoning
5. Risks and Limitations
6. Independent Conclusion
7. Confidence Level

Return a complete, structured report.
""".strip()

    # --------------------------------------------------------
    # Agent assignment
    # --------------------------------------------------------

    def assign_task(
        self,
        task_id: str,
        agent_ids: list[str] | None = None,
    ) -> ResearchTask:

        with self._edit_task(task_id) as task:

            if TaskStatus(task.status) not in {
                TaskStatus.PENDING,
                TaskStatus.FAILED,
            }:
                raise InvalidTaskTransitionError(
                    f"Cannot assign task in status: {task.status}"
                )

            selected_agents = agent_ids or list(
                self.config.agents.keys()
            )

            if not selected_agents:
                raise ValueError("At least one agent is required.")

            if len(selected_agents) != len(set(selected_agents)):
                raise ValueError("Duplicate agent IDs are not allowed.")

            for agent_id in selected_agents:
                if agent_id not in self.config.agents:
                    raise InvalidAgentError(agent_id)

            now = self._now()

            new_assignments = {}

            for agent_id in selected_agents:

                agent = self.config.agents[agent_id]

                new_assignments[agent_id] = AgentAssignment(
                    agent_id=agent_id,
                    agent_name=agent.name,
                    role=agent.role.value,
                    instruction=self._build_agent_instruction(
                        task,
                        agent,
                    ),
                    assigned_at=now,
                )

            task.assignments = new_assignments
            task.status = TaskStatus.ASSIGNED.value
            task.updated_at = now

        return self._tasks[task_id]

    # --------------------------------------------------------
    # Status management
    # --------------------------------------------------------

    def update_status(
        self,
        task_id: str,
        new_status: TaskStatus | str,
    ) -> ResearchTask:

        new_status_value = TaskStatus(new_status)

        with self._edit_task(task_id) as task:

            current_status = TaskStatus(task.status)

            allowed = self.VALID_TRANSITIONS[current_status]

            if new_status_value not in allowed:
                raise InvalidTaskTransitionError(
                    f"Invalid transition: "
                    f"{current_status.value} -> "
                    f"{new_status_value.value}"
                )

            task.status = new_status_value.value
            task.updated_at = self._now()

        return self._tasks[task_id]

    def start_task(self, task_id: str) -> ResearchTask:
        """同一个事务里同时推进任务状态与全部 assignment 状态。"""

        with self._edit_task(task_id) as task:

            current_status = TaskStatus(task.status)

            if TaskStatus.IN_PROGRESS not in self.VALID_TRANSITIONS[current_status]:
                raise InvalidTaskTransitionError(
                    f"Invalid transition: "
                    f"{current_status.value} -> "
                    f"{TaskStatus.IN_PROGRESS.value}"
                )

            task.status = TaskStatus.IN_PROGRESS.value

            for assignment in task.assignments.values():
                assignment.status = "in_progress"

            task.updated_at = self._now()

        return self._tasks[task_id]

    def submit_agent_report(
        self,
        task_id: str,
        agent_id: str,
        report_path: str | Path | None = None,
    ) -> ResearchTask:

        with self._edit_task(task_id) as task:

            if task.status != TaskStatus.IN_PROGRESS.value:
                raise InvalidTaskTransitionError(
                    "Task must be in progress before report submission."
                )

            if agent_id not in task.assignments:
                raise InvalidAgentError(
                    f"Agent {agent_id} is not assigned to this task."
                )

            assignment = task.assignments[agent_id]

            if assignment.status == "submitted":
                raise InvalidTaskTransitionError(
                    f"Agent {agent_id} already submitted a report."
                )

            assignment.status = "submitted"
            assignment.submitted_at = self._now()

            if report_path is not None:
                assignment.report_path = str(
                    Path(report_path).expanduser().resolve()
                )

            if all(
                item.status == "submitted"
                for item in task.assignments.values()
            ):
                task.status = TaskStatus.SUBMITTED.value

            task.updated_at = self._now()

        return self._tasks[task_id]

    # --------------------------------------------------------
    # Task queries
    # --------------------------------------------------------

    def get_task(self, task_id: str) -> ResearchTask:

        task = self._tasks.get(task_id)

        if task is None:
            raise TaskNotFoundError(task_id)

        return task

    def list_tasks(
        self,
        status: TaskStatus | str | None = None,
        task_type: TaskType | str | None = None,
    ) -> list[ResearchTask]:

        tasks = list(self._tasks.values())

        if status is not None:
            status_value = TaskStatus(status).value

            tasks = [
                task for task in tasks
                if task.status == status_value
            ]

        if task_type is not None:
            type_value = TaskType(task_type).value

            tasks = [
                task for task in tasks
                if task.task_type == type_value
            ]

        return sorted(
            tasks,
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_agent_instruction(
        self,
        task_id: str,
        agent_id: str,
    ) -> str:

        task = self.get_task(task_id)

        if agent_id not in task.assignments:
            raise InvalidAgentError(agent_id)

        return task.assignments[agent_id].instruction

    # --------------------------------------------------------
    # Task control
    # --------------------------------------------------------

    def cancel_task(self, task_id: str) -> ResearchTask:

        return self.update_status(
            task_id,
            TaskStatus.CANCELLED,
        )

    def retry_task(self, task_id: str) -> ResearchTask:

        task = self.get_task(task_id)

        if task.status != TaskStatus.FAILED.value:
            raise InvalidTaskTransitionError(
                "Only failed tasks can be retried."
            )

        return self.update_status(
            task_id,
            TaskStatus.PENDING,
        )

    # --------------------------------------------------------
    # Reporting
    # --------------------------------------------------------

    def get_task_summary(
        self,
        task_id: str,
    ) -> dict[str, Any]:

        task = self.get_task(task_id)

        return {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status,
            "task_type": task.task_type,
            "priority": task.priority,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "assigned_agents": list(
                task.assignments.keys()
            ),
            "submitted_agents": [
                agent_id
                for agent_id, assignment
                in task.assignments.items()
                if assignment.status == "submitted"
            ],
            "completion_ratio": (
                sum(
                    item.status == "submitted"
                    for item in task.assignments.values()
                ) / len(task.assignments)
                if task.assignments else 0.0
            ),
        }
