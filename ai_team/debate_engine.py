from __future__ import annotations

import json
import re
import uuid

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence


# ============================================================
# Exceptions
# ============================================================

class DebateEngineError(Exception):
    """Base exception for the debate engine."""


class DebateTaskNotFoundError(DebateEngineError):
    """Raised when the requested research task does not exist."""


class DebateNotRequiredError(DebateEngineError):
    """Raised when validation does not require a debate."""


class DebateNotFoundError(DebateEngineError):
    """Raised when a debate session cannot be found."""


class DebateStateError(DebateEngineError):
    """Raised when an operation is invalid for the current state."""


class DebateParticipantError(DebateEngineError):
    """Raised when an agent is not a participant in the debate."""


class DebateResponseError(DebateEngineError):
    """Raised when a submitted response is invalid."""


class DebatePersistenceError(DebateEngineError):
    """Raised when a debate cannot be persisted or loaded."""


# ============================================================
# Enums
# ============================================================

class DebateStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DebateRoundStatus(str, Enum):
    OPEN = "open"
    COMPLETED = "completed"


class DebatePosition(str, Enum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    NEUTRAL = "neutral"
    CLARIFY = "clarify"


class DebateConclusion(str, Enum):
    CONSENSUS = "consensus"
    PARTIAL_CONSENSUS = "partial_consensus"
    NO_CONSENSUS = "no_consensus"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


# ============================================================
# Constants
# ============================================================

DEFAULT_MAX_ROUNDS = 2
MAX_ALLOWED_ROUNDS = 10

DEFAULT_PARTICIPANTS = ("chatgpt", "grok", "hark")

VALID_AGENT_IDS = frozenset(DEFAULT_PARTICIPANTS)

DEFAULT_POSITION = DebatePosition.NEUTRAL

DEBATE_FILE_PREFIX = "debate_"
DEBATE_FILE_SUFFIX = ".json"


# ============================================================
# Utility functions
# ============================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _safe_identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} cannot be empty.")

    if len(value) > 128:
        raise ValueError(f"{field_name} is too long.")

    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", value):
        raise ValueError(
            f"{field_name} contains unsupported characters."
        )

    return value


def _safe_text(
    value: Any,
    field_name: str,
    *,
    required: bool = True,
    max_length: int = 50000,
) -> str:
    if value is None:
        value = ""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    value = value.strip()

    if required and not value:
        raise ValueError(f"{field_name} cannot be empty.")

    if len(value) > max_length:
        raise ValueError(
            f"{field_name} exceeds {max_length} characters."
        )

    return value


def _enum_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)

    return str(value)


def _json_safe(value: Any) -> Any:
    """
    Convert common Python objects into JSON-compatible values.

    This function deliberately avoids arbitrary object serialization.
    """
    if value is None:
        return None

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_safe(value.to_dict())

    if hasattr(value, "__dataclass_fields__"):
        return _json_safe(asdict(value))

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def _get_value(
    source: Any,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)

    return getattr(source, key, default)


def _normalize_agent_id(agent_id: Any) -> str:
    agent_id = _safe_identifier(agent_id, "agent_id").lower()

    if agent_id not in VALID_AGENT_IDS:
        raise DebateParticipantError(
            f"Unsupported agent_id: {agent_id}"
        )

    return agent_id


# ============================================================
# Data models
# ============================================================

@dataclass
class DebateMessage:
    message_id: str
    debate_id: str
    round_number: int
    agent_id: str
    position: str
    content: str
    evidence: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class DebateRound:
    round_number: int
    status: str = DebateRoundStatus.OPEN.value
    prompt: str = ""
    messages: list[DebateMessage] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    completed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "status": self.status,
            "prompt": self.prompt,
            "messages": [
                message.to_dict()
                for message in self.messages
            ],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class DebateSession:
    debate_id: str
    task_id: str
    validation_id: Optional[str]
    status: str
    participants: list[str]
    max_rounds: int
    current_round: int
    validation_payload: dict[str, Any]
    rounds: list[DebateRound] = field(default_factory=list)
    conclusion: Optional[str] = None
    conclusion_text: str = ""
    unresolved_issues: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    completed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "debate_id": self.debate_id,
            "task_id": self.task_id,
            "validation_id": self.validation_id,
            "status": self.status,
            "participants": list(self.participants),
            "max_rounds": self.max_rounds,
            "current_round": self.current_round,
            "validation_payload": _json_safe(
                self.validation_payload
            ),
            "rounds": [
                debate_round.to_dict()
                for debate_round in self.rounds
            ],
            "conclusion": self.conclusion,
            "conclusion_text": self.conclusion_text,
            "unresolved_issues": list(self.unresolved_issues),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


@dataclass
class DebateSummary:
    debate_id: str
    task_id: str
    status: str
    conclusion: Optional[str]
    participant_count: int
    round_count: int
    message_count: int
    unresolved_issue_count: int
    created_at: str
    completed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


# ============================================================
# Debate engine
# ============================================================

class DebateEngine:
    """
    Structured, manual multi-agent debate engine.

    The engine consumes Step 4 CrossValidator output and creates
    structured debate rounds.

    It does not call any AI provider and does not execute trades.
    """

    def __init__(
        self,
        task_manager: Any,
        cross_validator: Any,
        report_collector: Any = None,
        storage_dir: Optional[str | Path] = None,
        default_max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> None:
        if task_manager is None:
            raise ValueError("task_manager is required.")

        if cross_validator is None:
            raise ValueError("cross_validator is required.")

        if not hasattr(task_manager, "get_task"):
            raise TypeError(
                "task_manager must provide get_task()."
            )

        if not hasattr(cross_validator, "validate_task"):
            raise TypeError(
                "cross_validator must provide validate_task()."
            )

        if not hasattr(cross_validator, "export_debate_payload"):
            raise TypeError(
                "cross_validator must provide "
                "export_debate_payload()."
            )

        if not hasattr(cross_validator, "get_result"):
            raise TypeError(
                "cross_validator must provide get_result()."
            )

        if not isinstance(default_max_rounds, int):
            raise TypeError("default_max_rounds must be an integer.")

        if not 1 <= default_max_rounds <= MAX_ALLOWED_ROUNDS:
            raise ValueError(
                f"default_max_rounds must be between 1 and "
                f"{MAX_ALLOWED_ROUNDS}."
            )

        self.task_manager = task_manager
        self.cross_validator = cross_validator
        self.report_collector = report_collector
        self.default_max_rounds = default_max_rounds

        if storage_dir is None:
            collector_dir = getattr(
                report_collector,
                "storage_dir",
                None,
            )

            if collector_dir is not None:
                storage_dir = (
                    Path(collector_dir) / "_debates"
                )
            else:
                storage_dir = (
                    Path.cwd() / "data" / "ai_team" / "debates"
                )

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._sessions: dict[str, DebateSession] = {}

    # --------------------------------------------------------
    # Public API: create debate
    # --------------------------------------------------------

    def start_debate(
        self,
        task_id: str,
        validation_result: Any = None,
        validation_id: Optional[str] = None,
        participants: Optional[Sequence[str]] = None,
        max_rounds: Optional[int] = None,
        force: bool = False,
    ) -> DebateSession:
        """
        Create a debate session from a cross-validation result.

        If validation_result is omitted:
        - validation_id is used to load an existing result; or
        - validate_task(task_id) is called.

        By default, a debate is only created when the validation
        payload says requires_debate=True.

        Set force=True to create a debate even when validation
        does not explicitly require one.
        """
        task_id = _safe_identifier(task_id, "task_id")

        task = self.task_manager.get_task(task_id)

        if task is None:
            raise DebateTaskNotFoundError(
                f"Task not found: {task_id}"
            )

        if validation_result is None:
            if validation_id:
                validation_id = _safe_identifier(
                    validation_id,
                    "validation_id",
                )
                validation_result = (
                    self.cross_validator.get_result(validation_id)
                )
            else:
                validation_result = (
                    self.cross_validator.validate_task(task_id)
                )

        payload = self._build_validation_payload(
            validation_result
        )

        payload_task_id = payload.get("task_id")

        if payload_task_id and payload_task_id != task_id:
            raise DebateEngineError(
                "Validation result task_id does not match "
                "the requested task_id."
            )

        if not force and not payload.get("requires_debate", False):
            raise DebateNotRequiredError(
                "Cross-validation did not identify a need for debate."
            )

        resolved_participants = self._resolve_participants(
            payload,
            participants,
        )

        resolved_max_rounds = (
            self.default_max_rounds
            if max_rounds is None
            else max_rounds
        )

        if not isinstance(resolved_max_rounds, int):
            raise ValueError("max_rounds must be an integer.")

        if not 1 <= resolved_max_rounds <= MAX_ALLOWED_ROUNDS:
            raise ValueError(
                f"max_rounds must be between 1 and "
                f"{MAX_ALLOWED_ROUNDS}."
            )

        debate_id = _new_id("debate")

        first_round = DebateRound(
            round_number=1,
            status=DebateRoundStatus.OPEN.value,
            prompt=self._build_round_prompt(
                payload,
                round_number=1,
            ),
        )

        session = DebateSession(
            debate_id=debate_id,
            task_id=task_id,
            validation_id=payload.get("validation_id"),
            status=DebateStatus.IN_PROGRESS.value,
            participants=resolved_participants,
            max_rounds=resolved_max_rounds,
            current_round=1,
            validation_payload=payload,
            rounds=[first_round],
        )

        self._sessions[debate_id] = session
        self._touch(session)
        self.save_debate(session)

        return session

    def _build_validation_payload(
        self,
        validation_result: Any,
    ) -> dict[str, Any]:
        if validation_result is None:
            raise DebateEngineError(
                "A validation result is required."
            )

        if isinstance(validation_result, Mapping):
            payload = dict(validation_result)
        else:
            validation_id = _get_value(
                validation_result,
                "validation_id",
            )

            if not validation_id:
                raise DebateEngineError(
                    "Validation result must expose validation_id."
                )

            payload = self.cross_validator.export_debate_payload(
                validation_result
            )

        if not isinstance(payload, Mapping):
            raise DebateEngineError(
                "export_debate_payload() must return a mapping."
            )

        payload = _json_safe(dict(payload))

        payload.setdefault(
            "validation_id",
            _get_value(validation_result, "validation_id"),
        )

        payload.setdefault("conflicts", [])
        payload.setdefault("consensus", [])
        payload.setdefault("agent_analyses", [])
        payload.setdefault("agreement_score", None)
        payload.setdefault("requires_debate", False)

        if not isinstance(payload["conflicts"], list):
            raise DebateEngineError(
                "Validation payload conflicts must be a list."
            )

        if not isinstance(payload["consensus"], list):
            raise DebateEngineError(
                "Validation payload consensus must be a list."
            )

        if not isinstance(payload["agent_analyses"], list):
            raise DebateEngineError(
                "Validation payload agent_analyses must be a list."
            )

        return payload

    def _resolve_participants(
        self,
        payload: Mapping[str, Any],
        participants: Optional[Sequence[str]],
    ) -> list[str]:
        if participants is not None:
            raw_participants = list(participants)
        else:
            raw_participants = []

            for analysis in payload.get("agent_analyses", []):
                agent_id = _get_value(
                    analysis,
                    "agent_id",
                )

                if agent_id:
                    raw_participants.append(agent_id)

            if not raw_participants:
                raw_participants = list(DEFAULT_PARTICIPANTS)

        resolved: list[str] = []

        for agent_id in raw_participants:
            normalized = _normalize_agent_id(agent_id)

            if normalized not in resolved:
                resolved.append(normalized)

        if len(resolved) < 2:
            raise DebateParticipantError(
                "A debate requires at least two participants."
            )

        return resolved

    # --------------------------------------------------------
    # Prompt generation
    # --------------------------------------------------------

    def _build_round_prompt(
        self,
        payload: Mapping[str, Any],
        round_number: int,
    ) -> str:
        conflicts = payload.get("conflicts", [])
        consensus = payload.get("consensus", [])
        agreement_score = payload.get("agreement_score")

        lines = [
            f"AI TEAM DEBATE - ROUND {round_number}",
            "",
            "Research task:",
            str(payload.get("task_id", "Unknown task")),
            "",
            "Instructions:",
            "1. Review the disagreements identified below.",
            "2. State your position clearly.",
            "3. Provide verifiable evidence where possible.",
            "4. Identify assumptions and uncertainty.",
            "5. Explain what evidence would change your view.",
            "6. Do not fabricate data, sources, or financial figures.",
            "",
            "Cross-validation agreement score:",
            str(agreement_score),
            "",
            "Identified conflicts:",
        ]

        if conflicts:
            for index, conflict in enumerate(conflicts, start=1):
                lines.append(
                    f"{index}. {self._format_item(conflict)}"
                )
        else:
            lines.append("No explicit conflicts were provided.")

        lines.extend([
            "",
            "Existing consensus:",
        ])

        if consensus:
            for index, item in enumerate(consensus, start=1):
                lines.append(
                    f"{index}. {self._format_item(item)}"
                )
        else:
            lines.append("No consensus items were provided.")

        lines.extend([
            "",
            "Required response format:",
            "POSITION: support / oppose / neutral / clarify",
            "CORE_ARGUMENT:",
            "EVIDENCE:",
            "COUNTERARGUMENT:",
            "KEY_ASSUMPTIONS:",
            "WHAT_WOULD_CHANGE_MY_VIEW:",
            "CONFIDENCE: low / medium / high",
        ])

        return "\n".join(lines)

    @staticmethod
    def _format_item(item: Any) -> str:
        if isinstance(item, Mapping):
            preferred_keys = (
                "description",
                "claim_text",
                "claim",
                "summary",
                "reason",
                "text",
            )

            for key in preferred_keys:
                value = item.get(key)

                if value:
                    return str(value)

            return json.dumps(
                _json_safe(item),
                ensure_ascii=False,
                sort_keys=True,
            )

        return str(item)

    # --------------------------------------------------------
    # Public API: submit response
    # --------------------------------------------------------

    def submit_response(
        self,
        debate_id: str,
        agent_id: str,
        content: str,
        position: str = DEFAULT_POSITION.value,
        evidence: Optional[Iterable[str]] = None,
        round_number: Optional[int] = None,
    ) -> DebateMessage:
        debate_id = _safe_identifier(debate_id, "debate_id")
        agent_id = _normalize_agent_id(agent_id)
        content = _safe_text(
            content,
            "content",
            max_length=50000,
        )

        session = self.get_debate(debate_id)

        if session.status != DebateStatus.IN_PROGRESS.value:
            raise DebateStateError(
                "Cannot submit a response to a debate "
                "that is not in progress."
            )

        if agent_id not in session.participants:
            raise DebateParticipantError(
                f"{agent_id} is not a participant in this debate."
            )

        if round_number is None:
            round_number = session.current_round

        if not isinstance(round_number, int):
            raise DebateResponseError(
                "round_number must be an integer."
            )

        if round_number != session.current_round:
            raise DebateResponseError(
                "Responses can only be submitted to the current round."
            )

        current_round = self._get_current_round(session)

        if current_round.status != DebateRoundStatus.OPEN.value:
            raise DebateStateError(
                "The current debate round is not open."
            )

        existing = [
            message
            for message in current_round.messages
            if message.agent_id == agent_id
        ]

        if existing:
            raise DebateResponseError(
                f"{agent_id} has already submitted a response "
                f"for round {round_number}."
            )

        try:
            normalized_position = DebatePosition(
                _enum_value(position).lower()
            ).value
        except ValueError as exc:
            raise DebateResponseError(
                "position must be support, oppose, neutral, "
                "or clarify."
            ) from exc

        evidence_items: list[str] = []

        if evidence is not None:
            for item in evidence:
                evidence_text = _safe_text(
                    item,
                    "evidence item",
                    required=True,
                    max_length=5000,
                )

                if evidence_text not in evidence_items:
                    evidence_items.append(evidence_text)

        message = DebateMessage(
            message_id=_new_id("message"),
            debate_id=debate_id,
            round_number=round_number,
            agent_id=agent_id,
            position=normalized_position,
            content=content,
            evidence=evidence_items,
        )

        current_round.messages.append(message)

        self._touch(session)
        self.save_debate(session)

        return message

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------

    @staticmethod
    def _touch(session: DebateSession) -> None:
        session.updated_at = _utc_now()

    @staticmethod
    def _get_current_round(
        session: DebateSession,
    ) -> DebateRound:
        for debate_round in session.rounds:
            if debate_round.round_number == session.current_round:
                return debate_round

        raise DebateStateError(
            "Current round is missing from the debate session."
        )

    @staticmethod
    def _message_count(session: DebateSession) -> int:
        return sum(
            len(debate_round.messages)
            for debate_round in session.rounds
        )


    # --------------------------------------------------------
    # Public API: advance debate
    # --------------------------------------------------------

    def advance_round(
        self,
        debate_id: str,
        allow_incomplete: bool = False,
    ) -> DebateRound:
        """
        Complete the current round and open the next round.

        By default, every participant must submit one response.
        Set allow_incomplete=True to advance with missing responses.
        """
        debate_id = _safe_identifier(debate_id, "debate_id")
        session = self.get_debate(debate_id)

        if session.status != DebateStatus.IN_PROGRESS.value:
            raise DebateStateError(
                "Only an in-progress debate can advance."
            )

        current_round = self._get_current_round(session)

        if current_round.status != DebateRoundStatus.OPEN.value:
            raise DebateStateError(
                "The current round is already completed."
            )

        submitted_agents = {
            message.agent_id
            for message in current_round.messages
        }

        missing_agents = [
            agent_id
            for agent_id in session.participants
            if agent_id not in submitted_agents
        ]

        if missing_agents and not allow_incomplete:
            raise DebateStateError(
                "Missing responses from: "
                + ", ".join(missing_agents)
            )

        current_round.status = DebateRoundStatus.COMPLETED.value
        current_round.completed_at = _utc_now()

        if session.current_round >= session.max_rounds:
            self._touch(session)
            self.save_debate(session)

            raise DebateStateError(
                "Maximum debate rounds reached. "
                "Finalize the debate instead."
            )

        next_round_number = session.current_round + 1

        next_round = DebateRound(
            round_number=next_round_number,
            status=DebateRoundStatus.OPEN.value,
            prompt=self._build_follow_up_prompt(
                session,
                next_round_number,
            ),
        )

        session.rounds.append(next_round)
        session.current_round = next_round_number

        self._touch(session)
        self.save_debate(session)

        return next_round

    def _build_follow_up_prompt(
        self,
        session: DebateSession,
        round_number: int,
    ) -> str:
        previous_round = session.rounds[-1]

        lines = [
            f"AI TEAM DEBATE - ROUND {round_number}",
            "",
            "Review the responses from the previous round.",
            "Address the strongest counterarguments directly.",
            "Correct any unsupported claims.",
            "Distinguish verified facts from assumptions.",
            "State whether your position has changed.",
            "",
            "Previous round responses:",
        ]

        if previous_round.messages:
            for message in previous_round.messages:
                lines.extend([
                    "",
                    f"Agent: {message.agent_id}",
                    f"Position: {message.position}",
                    f"Response: {message.content}",
                    "Evidence:",
                ])

                if message.evidence:
                    for evidence_item in message.evidence:
                        lines.append(f"- {evidence_item}")
                else:
                    lines.append("- No evidence supplied.")

        else:
            lines.append("No responses were submitted.")

        lines.extend([
            "",
            "Required response format:",
            "POSITION: support / oppose / neutral / clarify",
            "POSITION_CHANGED: yes / no",
            "CORE_ARGUMENT:",
            "RESPONSE_TO_COUNTERARGUMENTS:",
            "NEW_EVIDENCE:",
            "REMAINING_UNCERTAINTY:",
            "CONFIDENCE: low / medium / high",
        ])

        return "\n".join(lines)

    # --------------------------------------------------------
    # Public API: finalize debate
    # --------------------------------------------------------

    def finalize_debate(
        self,
        debate_id: str,
        conclusion: str,
        conclusion_text: str,
        unresolved_issues: Optional[Iterable[str]] = None,
    ) -> DebateSession:
        debate_id = _safe_identifier(debate_id, "debate_id")
        session = self.get_debate(debate_id)

        if session.status != DebateStatus.IN_PROGRESS.value:
            raise DebateStateError(
                "Only an in-progress debate can be finalized."
            )

        try:
            normalized_conclusion = DebateConclusion(
                _enum_value(conclusion).lower()
            ).value
        except ValueError as exc:
            raise DebateResponseError(
                "conclusion must be one of: consensus, "
                "partial_consensus, no_consensus, "
                "insufficient_evidence."
            ) from exc

        conclusion_text = _safe_text(
            conclusion_text,
            "conclusion_text",
            max_length=20000,
        )

        issues: list[str] = []

        if unresolved_issues is not None:
            for issue in unresolved_issues:
                issue_text = _safe_text(
                    issue,
                    "unresolved issue",
                    max_length=5000,
                )

                if issue_text not in issues:
                    issues.append(issue_text)

        current_round = self._get_current_round(session)

        if current_round.status == DebateRoundStatus.OPEN.value:
            current_round.status = DebateRoundStatus.COMPLETED.value
            current_round.completed_at = _utc_now()

        session.status = DebateStatus.COMPLETED.value
        session.conclusion = normalized_conclusion
        session.conclusion_text = conclusion_text
        session.unresolved_issues = issues
        session.completed_at = _utc_now()

        self._touch(session)
        self.save_debate(session)

        return session

    # --------------------------------------------------------
    # Public API: cancel debate
    # --------------------------------------------------------

    def cancel_debate(
        self,
        debate_id: str,
        reason: str = "",
    ) -> DebateSession:
        debate_id = _safe_identifier(debate_id, "debate_id")
        session = self.get_debate(debate_id)

        if session.status != DebateStatus.IN_PROGRESS.value:
            raise DebateStateError(
                "Only an in-progress debate can be cancelled."
            )

        reason = _safe_text(
            reason,
            "reason",
            required=False,
            max_length=5000,
        )

        session.status = DebateStatus.CANCELLED.value

        if reason:
            session.conclusion_text = (
                f"Debate cancelled: {reason}"
            )

        current_round = self._get_current_round(session)

        if current_round.status == DebateRoundStatus.OPEN.value:
            current_round.status = DebateRoundStatus.COMPLETED.value
            current_round.completed_at = _utc_now()

        session.completed_at = _utc_now()

        self._touch(session)
        self.save_debate(session)

        return session

    # --------------------------------------------------------
    # Public API: read and list
    # --------------------------------------------------------

    def get_debate(self, debate_id: str) -> DebateSession:
        debate_id = _safe_identifier(debate_id, "debate_id")

        if debate_id in self._sessions:
            return self._sessions[debate_id]

        path = self._debate_path(debate_id)

        if not path.exists():
            raise DebateNotFoundError(
                f"Debate not found: {debate_id}"
            )

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            session = self._session_from_dict(data)
            self._sessions[session.debate_id] = session

            return session

        except DebateEngineError:
            raise
        except Exception as exc:
            raise DebatePersistenceError(
                f"Could not load debate {debate_id}: {exc}"
            ) from exc

    def list_debates(
        self,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[DebateSummary]:
        normalized_task_id = None

        if task_id is not None:
            normalized_task_id = _safe_identifier(
                task_id,
                "task_id",
            )

        normalized_status = None

        if status is not None:
            normalized_status = _enum_value(status).lower()

            allowed_statuses = {
                item.value for item in DebateStatus
            }

            if normalized_status not in allowed_statuses:
                raise ValueError(
                    f"status must be one of: "
                    f"{', '.join(sorted(allowed_statuses))}"
                )

        sessions: dict[str, DebateSession] = dict(self._sessions)

        for path in self.storage_dir.glob(
            f"{DEBATE_FILE_PREFIX}*{DEBATE_FILE_SUFFIX}"
        ):
            debate_id = path.stem[len(DEBATE_FILE_PREFIX):]

            if debate_id in sessions:
                continue

            try:
                session = self.get_debate(debate_id)
                sessions[session.debate_id] = session
            except DebateEngineError:
                continue

        summaries: list[DebateSummary] = []

        for session in sessions.values():
            if (
                normalized_task_id is not None
                and session.task_id != normalized_task_id
            ):
                continue

            if (
                normalized_status is not None
                and session.status != normalized_status
            ):
                continue

            summaries.append(
                self._build_summary(session)
            )

        summaries.sort(
            key=lambda item: item.created_at,
            reverse=True,
        )

        return summaries

    @staticmethod
    def _build_summary(
        session: DebateSession,
    ) -> DebateSummary:
        return DebateSummary(
            debate_id=session.debate_id,
            task_id=session.task_id,
            status=session.status,
            conclusion=session.conclusion,
            participant_count=len(session.participants),
            round_count=len(session.rounds),
            message_count=DebateEngine._message_count(session),
            unresolved_issue_count=len(
                session.unresolved_issues
            ),
            created_at=session.created_at,
            completed_at=session.completed_at,
        )

    # --------------------------------------------------------
    # Public API: export
    # --------------------------------------------------------

    def export_debate(
        self,
        debate_id: str,
    ) -> dict[str, Any]:
        session = self.get_debate(debate_id)
        return session.to_dict()

    def export_debate_markdown(
        self,
        debate_id: str,
    ) -> str:
        session = self.get_debate(debate_id)

        lines = [
            "# AI Team Debate Report",
            "",
            f"- Debate ID: {session.debate_id}",
            f"- Task ID: {session.task_id}",
            f"- Validation ID: {session.validation_id or 'N/A'}",
            f"- Status: {session.status}",
            f"- Participants: {', '.join(session.participants)}",
            f"- Rounds: {len(session.rounds)}",
            "",
            "## Cross-validation overview",
            "",
            f"- Agreement score: "
            f"{session.validation_payload.get('agreement_score')}",
            f"- Conflicts: "
            f"{len(session.validation_payload.get('conflicts', []))}",
            f"- Consensus items: "
            f"{len(session.validation_payload.get('consensus', []))}",
            "",
        ]

        for debate_round in session.rounds:
            lines.extend([
                f"## Round {debate_round.round_number}",
                "",
                f"Status: {debate_round.status}",
                "",
                "### Round prompt",
                "",
                debate_round.prompt,
                "",
                "### Agent responses",
                "",
            ])

            if not debate_round.messages:
                lines.extend([
                    "No responses submitted.",
                    "",
                ])

            for message in debate_round.messages:
                lines.extend([
                    f"#### {message.agent_id}",
                    "",
                    f"- Position: {message.position}",
                    f"- Submitted: {message.created_at}",
                    "",
                    message.content,
                    "",
                    "Evidence:",
                ])

                if message.evidence:
                    for evidence_item in message.evidence:
                        lines.append(f"- {evidence_item}")
                else:
                    lines.append("- No evidence supplied.")

                lines.append("")

        lines.extend([
            "## Final conclusion",
            "",
            f"- Conclusion: {session.conclusion or 'Not finalized'}",
            "",
            session.conclusion_text or "No final conclusion.",
            "",
            "## Unresolved issues",
            "",
        ])

        if session.unresolved_issues:
            for issue in session.unresolved_issues:
                lines.append(f"- {issue}")
        else:
            lines.append("None recorded.")

        lines.append("")
        return "\n".join(lines)

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def save_debate(
        self,
        session: DebateSession,
    ) -> Path:
        if not isinstance(session, DebateSession):
            raise TypeError(
                "session must be a DebateSession."
            )

        path = self._debate_path(session.debate_id)

        try:
            self.storage_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary_path = path.with_suffix(".tmp")

            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    session.to_dict(),
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            temporary_path.replace(path)
            self._sessions[session.debate_id] = session

            return path

        except Exception as exc:
            raise DebatePersistenceError(
                f"Could not save debate {session.debate_id}: {exc}"
            ) from exc

    def _debate_path(self, debate_id: str) -> Path:
        debate_id = _safe_identifier(
            debate_id,
            "debate_id",
        )

        # debate_id 本身带 "debate_" 前缀，落盘时只加一次，
        # 避免出现 debate_debate_xxx.json。
        if debate_id.startswith(DEBATE_FILE_PREFIX):
            debate_id = debate_id[len(DEBATE_FILE_PREFIX):]

        return self.storage_dir / (
            f"{DEBATE_FILE_PREFIX}{debate_id}"
            f"{DEBATE_FILE_SUFFIX}"
        )

    @staticmethod
    def _session_from_dict(
        data: Mapping[str, Any],
    ) -> DebateSession:
        try:
            rounds: list[DebateRound] = []

            for round_data in data.get("rounds", []):
                messages = [
                    DebateMessage(
                        message_id=item["message_id"],
                        debate_id=item["debate_id"],
                        round_number=int(item["round_number"]),
                        agent_id=item["agent_id"],
                        position=item["position"],
                        content=item["content"],
                        evidence=list(item.get("evidence", [])),
                        created_at=item.get(
                            "created_at",
                            _utc_now(),
                        ),
                    )
                    for item in round_data.get("messages", [])
                ]

                rounds.append(
                    DebateRound(
                        round_number=int(
                            round_data["round_number"]
                        ),
                        status=round_data.get(
                            "status",
                            DebateRoundStatus.OPEN.value,
                        ),
                        prompt=round_data.get("prompt", ""),
                        messages=messages,
                        created_at=round_data.get(
                            "created_at",
                            _utc_now(),
                        ),
                        completed_at=round_data.get(
                            "completed_at"
                        ),
                    )
                )

            session = DebateSession(
                debate_id=data["debate_id"],
                task_id=data["task_id"],
                validation_id=data.get("validation_id"),
                status=data["status"],
                participants=list(data["participants"]),
                max_rounds=int(data["max_rounds"]),
                current_round=int(data["current_round"]),
                validation_payload=dict(
                    data.get("validation_payload", {})
                ),
                rounds=rounds,
                conclusion=data.get("conclusion"),
                conclusion_text=data.get(
                    "conclusion_text",
                    "",
                ),
                unresolved_issues=list(
                    data.get("unresolved_issues", [])
                ),
                created_at=data.get(
                    "created_at",
                    _utc_now(),
                ),
                updated_at=data.get(
                    "updated_at",
                    _utc_now(),
                ),
                completed_at=data.get("completed_at"),
            )

            if not session.rounds:
                raise ValueError(
                    "Persisted debate has no rounds."
                )

            return session

        except Exception as exc:
            raise DebatePersistenceError(
                f"Invalid persisted debate data: {exc}"
            ) from exc
