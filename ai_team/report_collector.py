
"""
AI Hedge Fund OS V3.10
Multi-AI Collaboration Engine

Step 3: Report Collector

Features:
- Collect reports from ChatGPT, Grok and Hark
- Validate report structure
- Save original Markdown reports
- Persist report metadata as JSON
- Associate reports with research tasks
- Prevent duplicate submissions
- Synchronize submission status with TaskManager
- Query and retrieve historical reports
- Generate collection summaries

Python >= 3.11
Standard library only.
No AI API required.
No live trading interface.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from evolution.file_lock import FileLock

from ai_team.config import get_default_config
from ai_team.task_manager import (
    InvalidTaskTransitionError,
    TaskManager,
    TaskNotFoundError,
    TaskStatus,
)


logger = logging.getLogger(__name__)


# ============================================================
# Exceptions
# ============================================================

class ReportCollectorError(Exception):
    """Base exception for report collection."""


class ReportNotFoundError(ReportCollectorError):
    """Raised when a report cannot be found."""


class InvalidReportError(ReportCollectorError):
    """Raised when report data is invalid."""


class DuplicateReportError(ReportCollectorError):
    """Raised when an agent submits a duplicate report."""


class ReportPersistenceError(ReportCollectorError):
    """Raised when report persistence fails."""


class ReportTaskStateError(ReportCollectorError):
    """Raised when task state prevents report submission."""


# ============================================================
# Enums
# ============================================================

class ReportFormat(str, Enum):
    MARKDOWN = "markdown"
    TEXT = "text"


class ReportQuality(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    EMPTY = "empty"


# ============================================================
# Constants
# ============================================================

DEFAULT_REQUIRED_SECTIONS = (
    "Executive Summary",
    "Key Findings",
    "Evidence and Sources",
    "Analytical Reasoning",
    "Risks and Limitations",
    "Independent Conclusion",
    "Confidence Level",
)

AGENT_IDS = (
    "chatgpt",
    "grok",
    "hark",
)


# ============================================================
# Data models
# ============================================================

@dataclass
class ReportValidation:
    """Result of report structure validation."""

    is_valid: bool
    quality: str

    total_characters: int
    total_words: int

    found_sections: list[str] = field(
        default_factory=list
    )

    missing_sections: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportRecord:
    """Persistent metadata for one submitted AI report."""

    report_id: str
    task_id: str

    agent_id: str
    agent_name: str
    agent_role: str

    title: str
    format: str

    report_path: str
    metadata_path: str

    quality: str
    validation: dict[str, Any]

    total_characters: int
    total_words: int

    created_at: str

    source: str = "manual"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ReportRecord:

        return cls(**data)


# ============================================================
# Report collector
# ============================================================

class ReportCollector:
    """
    Central report collection service.

    This module does not call external AI APIs.

    Free collaboration workflow:

        1. TaskManager creates a task.
        2. Three AI agents independently generate reports.
        3. User copies report text into ReportCollector.
        4. ReportCollector validates and stores the report.
        5. TaskManager receives submission status.

    Expected task state:
        IN_PROGRESS

    Expected agent IDs:
        chatgpt
        grok
        hark
    """

    def __init__(
        self,
        task_manager: TaskManager,
        storage_dir: Path | str | None = None,
        required_sections: tuple[str, ...] | None = None,
        strict_validation: bool = False,
    ) -> None:

        if task_manager is None:
            raise ValueError(
                "task_manager cannot be None."
            )

        self.task_manager = task_manager

        if storage_dir is None:
            config = get_default_config()
            storage_dir = config.reports_dir

        self.storage_dir = Path(
            storage_dir
        ).expanduser().resolve()

        self.storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.required_sections = (
            required_sections
            if required_sections is not None
            else DEFAULT_REQUIRED_SECTIONS
        )

        self.strict_validation = strict_validation

        self._validate_required_sections()

    # --------------------------------------------------------
    # Utility methods
    # --------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _safe_identifier(
        value: str,
        field_name: str,
    ) -> str:

        if not isinstance(value, str):
            raise ValueError(
                f"{field_name} must be a string."
            )

        value = value.strip()

        if not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}",
            value,
        ):
            raise ValueError(
                f"Invalid {field_name}: {value}"
            )

        return value

    @staticmethod
    def _validate_text(
        value: str,
        field_name: str,
    ) -> str:

        if not isinstance(value, str):
            raise ValueError(
                f"{field_name} must be a string."
            )

        value = value.strip()

        if not value:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return value

    def _validate_required_sections(self) -> None:

        if not isinstance(
            self.required_sections,
            tuple,
        ):
            raise ValueError(
                "required_sections must be a tuple."
            )

        if not self.required_sections:
            raise ValueError(
                "required_sections cannot be empty."
            )

        for section in self.required_sections:

            if not isinstance(section, str) or not section.strip():
                raise ValueError(
                    "Every required section must be a non-empty string."
                )

    @staticmethod
    def _safe_filename(value: str) -> str:

        safe = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            value,
        )

        return safe.strip("_")[:100]

    @staticmethod
    def _count_words(content: str) -> int:

        return len(
            re.findall(
                r"\b[\w'-]+\b|[\u4e00-\u9fff]",
                content,
                flags=re.UNICODE,
            )
        )

    # --------------------------------------------------------
    # Paths
    # --------------------------------------------------------

    def _task_report_dir(
        self,
        task_id: str,
    ) -> Path:

        safe_task_id = self._safe_identifier(
            task_id,
            "task_id",
        )

        return self.storage_dir / safe_task_id

    def _metadata_path(
        self,
        report_id: str,
    ) -> Path:

        safe_report_id = self._safe_identifier(
            report_id,
            "report_id",
        )

        return (
            self.storage_dir
            / "_metadata"
            / f"{safe_report_id}.json"
        )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def validate_report(
        self,
        content: str,
    ) -> ReportValidation:

        if not isinstance(content, str):
            raise InvalidReportError(
                "Report content must be a string."
            )

        normalized = content.strip()

        if not normalized:

            return ReportValidation(
                is_valid=False,
                quality=ReportQuality.EMPTY.value,
                total_characters=0,
                total_words=0,
                warnings=[
                    "Report content is empty."
                ],
            )

        found_sections = []
        missing_sections = []

        lines = normalized.splitlines()

        normalized_lines = [
            re.sub(
                r"^\s{0,3}#{1,6}\s*",
                "",
                line.strip(),
            ).strip().rstrip("#").strip().lower()
            for line in lines
        ]

        for section in self.required_sections:

            expected = section.strip().lower()

            found = any(
                line == expected
                for line in normalized_lines
            )

            if found:
                found_sections.append(section)
            else:
                missing_sections.append(section)

        warnings = []

        if missing_sections:
            warnings.append(
                "Some required report sections are missing."
            )

        if len(normalized) < 100:
            warnings.append(
                "Report content is unusually short."
            )

        quality = (
            ReportQuality.COMPLETE.value
            if not missing_sections
            else ReportQuality.INCOMPLETE.value
        )

        return ReportValidation(
            is_valid=True,
            quality=quality,
            total_characters=len(normalized),
            total_words=self._count_words(normalized),
            found_sections=found_sections,
            missing_sections=missing_sections,
            warnings=warnings,
        )

    # --------------------------------------------------------
    # Report index
    # --------------------------------------------------------

    def _load_all_records(self) -> list[ReportRecord]:

        metadata_dir = self.storage_dir / "_metadata"

        if not metadata_dir.exists():
            return []

        records = []

        for path in metadata_dir.glob("*.json"):

            try:
                with path.open(
                    "r",
                    encoding="utf-8",
                ) as file:

                    data = json.load(file)

                record = ReportRecord.from_dict(data)

                if path.stem != record.report_id:
                    raise ValueError(
                        "Metadata filename and report ID mismatch."
                    )

                records.append(record)

            except (
                OSError,
                json.JSONDecodeError,
                TypeError,
                ValueError,
                KeyError,
            ) as exc:

                logger.warning(
                    "Unable to load report metadata %s: %s",
                    path,
                    exc,
                )

        return records

    def _find_duplicate(
        self,
        task_id: str,
        agent_id: str,
    ) -> ReportRecord | None:

        for record in self._load_all_records():

            if (
                record.task_id == task_id
                and record.agent_id == agent_id
            ):
                return record

        return None

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def _write_text_atomic(
        self,
        path: Path,
        content: str,
    ) -> None:

        temp_path = path.with_name(
            f".{path.name}.{uuid.uuid4().hex}.tmp"
        )

        try:

            with temp_path.open(
                "w",
                encoding="utf-8",
            ) as file:

                file.write(content)
                file.flush()

            temp_path.replace(path)

        except OSError as exc:

            temp_path.unlink(missing_ok=True)

            raise ReportPersistenceError(
                f"Unable to write file: {path}"
            ) from exc

    def _write_json_atomic(
        self,
        path: Path,
        data: dict[str, Any],
    ) -> None:

        try:

            serialized = json.dumps(
                data,
                ensure_ascii=False,
                indent=4,
            )

        except (TypeError, ValueError) as exc:

            raise ReportPersistenceError(
                "Unable to serialize report metadata."
            ) from exc

        self._write_text_atomic(
            path,
            serialized,
        )

    # --------------------------------------------------------
    # Task and agent validation
    # --------------------------------------------------------

    def _get_valid_assignment(
        self,
        task_id: str,
        agent_id: str,
    ):

        try:

            task = self.task_manager.get_task(
                task_id
            )

        except TaskNotFoundError:
            raise

        if agent_id not in task.assignments:
            raise InvalidReportError(
                f"Agent {agent_id} is not assigned to task {task_id}."
            )

        if task.status != TaskStatus.IN_PROGRESS.value:
            raise ReportTaskStateError(
                "Task must be IN_PROGRESS before report submission."
            )

        assignment = task.assignments[agent_id]

        if assignment.status == "submitted":
            raise DuplicateReportError(
                f"Agent {agent_id} has already submitted a report."
            )

        return task, assignment

    # --------------------------------------------------------
    # Main collection method
    # --------------------------------------------------------

    def collect_report(
        self,
        task_id: str,
        agent_id: str,
        content: str,
        title: str | None = None,
        report_format: ReportFormat | str = ReportFormat.MARKDOWN,
        source: str = "manual",
        notes: str = "",
        allow_incomplete: bool = True,
    ) -> ReportRecord:
        """
        Collect a report under a process-level lock.

        Lock granularity: task_id + agent_id.
        Same task/agent submissions are serialized, different agents
        can submit concurrently.
        """

        task_id = self._safe_identifier(
            task_id,
            "task_id",
        )

        agent_id = self._safe_identifier(
            agent_id,
            "agent_id",
        )

        if agent_id not in AGENT_IDS:
            raise InvalidReportError(
                f"Unsupported agent: {agent_id}"
            )

        lock_key = f"{task_id}\0{agent_id}"

        lock_hash = hashlib.sha256(
            lock_key.encode("utf-8")
        ).hexdigest()[:16]

        lock_dir = self.storage_dir / "_locks"

        lock_target = lock_dir / f"report_{lock_hash}"

        with FileLock(
            lock_target,
            timeout=10.0,
            poll_interval=0.05,
        ):

            return self._collect_report_unlocked(
                task_id=task_id,
                agent_id=agent_id,
                content=content,
                title=title,
                report_format=report_format,
                source=source,
                notes=notes,
                allow_incomplete=allow_incomplete,
            )

    def _collect_report_unlocked(
        self,
        task_id: str,
        agent_id: str,
        content: str,
        title: str | None = None,
        report_format: ReportFormat | str = ReportFormat.MARKDOWN,
        source: str = "manual",
        notes: str = "",
        allow_incomplete: bool = True,
    ) -> ReportRecord:
        """
        Original report collection logic.

        Caller must hold the task_id + agent_id FileLock.
        """

        task_id = self._safe_identifier(
            task_id,
            "task_id",
        )

        agent_id = self._safe_identifier(
            agent_id,
            "agent_id",
        )

        if agent_id not in AGENT_IDS:
            raise InvalidReportError(
                f"Unsupported agent: {agent_id}"
            )

        # 报告正文校验失败属于报告数据非法，
        # 统一抛 InvalidReportError（与测试契约一致）。
        try:
            content = self._validate_text(
                content,
                "content",
            )
        except ValueError as exc:
            raise InvalidReportError(str(exc)) from exc

        if title is None:
            title = f"{agent_id} research report"

        title = self._validate_text(
            title,
            "title",
        )

        source = self._validate_text(
            source,
            "source",
        )

        if not isinstance(notes, str):
            raise ValueError(
                "notes must be a string."
            )

        try:

            format_value = ReportFormat(
                report_format
            ).value

        except ValueError as exc:

            raise ValueError(
                f"Unsupported report format: {report_format}"
            ) from exc

        if not isinstance(allow_incomplete, bool):
            raise ValueError(
                "allow_incomplete must be a boolean."
            )

        task, assignment = self._get_valid_assignment(
            task_id,
            agent_id,
        )

        duplicate = self._find_duplicate(
            task_id,
            agent_id,
        )

        if duplicate is not None:
            raise DuplicateReportError(
                f"Report already exists: {duplicate.report_id}"
            )

        validation = self.validate_report(
            content
        )

        if not validation.is_valid:
            raise InvalidReportError(
                "Report content failed validation."
            )

        if (
            self.strict_validation
            and validation.quality
            != ReportQuality.COMPLETE.value
        ):
            raise InvalidReportError(
                "Report is missing required sections."
            )

        if (
            not allow_incomplete
            and validation.quality
            != ReportQuality.COMPLETE.value
        ):
            raise InvalidReportError(
                "Incomplete report submission is not allowed."
            )

        report_id = (
            "RPT-"
            + datetime.now(timezone.utc).strftime("%Y%m%d")
            + "-"
            + uuid.uuid4().hex[:10].upper()
        )

        task_dir = self._task_report_dir(
            task_id
        )

        task_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = (
            self._safe_filename(agent_id)
            + "_"
            + report_id
        )

        report_path = task_dir / f"{filename}.md"

        metadata_path = self._metadata_path(
            report_id
        )

        metadata_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        record = ReportRecord(
            report_id=report_id,
            task_id=task_id,
            agent_id=agent_id,
            agent_name=assignment.agent_name,
            agent_role=assignment.role,
            title=title,
            format=format_value,
            report_path=str(report_path.resolve()),
            metadata_path=str(metadata_path.resolve()),
            quality=validation.quality,
            validation=validation.to_dict(),
            total_characters=validation.total_characters,
            total_words=validation.total_words,
            created_at=self._now(),
            source=source,
            notes=notes,
        )

        report_written = False
        metadata_written = False

        try:

            self._write_text_atomic(
                report_path,
                content,
            )

            report_written = True

            self._write_json_atomic(
                metadata_path,
                record.to_dict(),
            )

            metadata_written = True

            self.task_manager.submit_agent_report(
                task_id=task_id,
                agent_id=agent_id,
                report_path=report_path,
            )

        except Exception as exc:

            if metadata_written:
                metadata_path.unlink(
                    missing_ok=True
                )

            if report_written:
                report_path.unlink(
                    missing_ok=True
                )

            # 兜底处理：即使其他调用路径已经提交，
            # 也向当前调用者统一报告重复提交。
            if isinstance(
                exc,
                InvalidTaskTransitionError,
            ):
                raise DuplicateReportError(
                    f"Agent {agent_id} has already submitted "
                    f"a report for task {task_id}."
                ) from exc

            if isinstance(
                exc,
                (
                    DuplicateReportError,
                    InvalidReportError,
                    ReportTaskStateError,
                    ReportPersistenceError,
                ),
            ):
                raise

            raise ReportCollectorError(
                f"Failed to collect report for {task_id}."
            ) from exc

        logger.info(
            "Report collected: task=%s agent=%s report=%s",
            task_id,
            agent_id,
            report_id,
        )

        return record

    # --------------------------------------------------------
    # Report retrieval
    # --------------------------------------------------------

    def get_report(
        self,
        report_id: str,
    ) -> ReportRecord:

        report_id = self._safe_identifier(
            report_id,
            "report_id",
        )

        path = self._metadata_path(
            report_id
        )

        if not path.exists():
            raise ReportNotFoundError(
                f"Report not found: {report_id}"
            )

        try:

            with path.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

            return ReportRecord.from_dict(data)

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:

            raise ReportPersistenceError(
                f"Unable to read report metadata: {report_id}"
            ) from exc

    def read_report(
        self,
        report_id: str,
    ) -> str:

        record = self.get_report(
            report_id
        )

        path = Path(
            record.report_path
        ).resolve()

        try:
            path.relative_to(
                self.storage_dir.resolve()
            )
        except ValueError as exc:
            raise ReportPersistenceError(
                "Report path is outside the report storage directory."
            ) from exc

        if not path.is_file():
            raise ReportNotFoundError(
                f"Report file missing: {report_id}"
            )

        try:

            return path.read_text(
                encoding="utf-8"
            )

        except OSError as exc:

            raise ReportPersistenceError(
                f"Unable to read report file: {report_id}"
            ) from exc

    # --------------------------------------------------------
    # Report listing
    # --------------------------------------------------------

    def list_reports(
        self,
        task_id: str | None = None,
        agent_id: str | None = None,
        quality: ReportQuality | str | None = None,
    ) -> list[ReportRecord]:

        if task_id is not None:
            task_id = self._safe_identifier(
                task_id,
                "task_id",
            )

        if agent_id is not None:
            agent_id = self._safe_identifier(
                agent_id,
                "agent_id",
            )

        quality_value = None

        if quality is not None:
            quality_value = ReportQuality(
                quality
            ).value

        records = self._load_all_records()

        if task_id is not None:
            records = [
                item for item in records
                if item.task_id == task_id
            ]

        if agent_id is not None:
            records = [
                item for item in records
                if item.agent_id == agent_id
            ]

        if quality_value is not None:
            records = [
                item for item in records
                if item.quality == quality_value
            ]

        return sorted(
            records,
            key=lambda item: item.created_at,
            reverse=True,
        )

    # --------------------------------------------------------
    # Collection summary
    # --------------------------------------------------------

    def get_collection_summary(
        self,
        task_id: str,
    ) -> dict[str, Any]:

        task_id = self._safe_identifier(
            task_id,
            "task_id",
        )

        task = self.task_manager.get_task(
            task_id
        )

        reports = self.list_reports(
            task_id=task_id
        )

        submitted_agents = {
            record.agent_id
            for record in reports
        }

        assigned_agents = set(
            task.assignments.keys()
        )

        missing_agents = sorted(
            assigned_agents - submitted_agents
        )

        complete_count = sum(
            record.quality == ReportQuality.COMPLETE.value
            for record in reports
        )

        incomplete_count = sum(
            record.quality == ReportQuality.INCOMPLETE.value
            for record in reports
        )

        return {
            "task_id": task_id,
            "task_title": task.title,
            "task_status": task.status,
            "assigned_agents": sorted(
                assigned_agents
            ),
            "submitted_agents": sorted(
                submitted_agents
            ),
            "missing_agents": missing_agents,
            "total_assigned": len(
                assigned_agents
            ),
            "total_submitted": len(
                reports
            ),
            "total_missing": len(
                missing_agents
            ),
            "complete_reports": complete_count,
            "incomplete_reports": incomplete_count,
            "completion_ratio": (
                len(submitted_agents) / len(assigned_agents)
                if assigned_agents else 0.0
            ),
            "reports": [
                record.to_dict()
                for record in reports
            ],
        }
