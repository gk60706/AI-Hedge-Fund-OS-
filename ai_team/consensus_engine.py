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

class ConsensusEngineError(Exception):
    """Base exception for consensus engine errors."""


class ConsensusTaskNotFoundError(ConsensusEngineError):
    """Raised when a research task does not exist."""


class ConsensusValidationError(ConsensusEngineError):
    """Raised when validation input is invalid."""


class ConsensusDebateError(ConsensusEngineError):
    """Raised when debate input is invalid or unavailable."""


class ConsensusNotFoundError(ConsensusEngineError):
    """Raised when a consensus report cannot be found."""


class ConsensusStateError(ConsensusEngineError):
    """Raised when a consensus operation is invalid."""


class ConsensusPersistenceError(ConsensusEngineError):
    """Raised when consensus persistence fails."""


# ============================================================
# Enums
# ============================================================

class ConsensusStatus(str, Enum):
    CONSENSUS = "consensus"
    PARTIAL_CONSENSUS = "partial_consensus"
    NO_CONSENSUS = "no_consensus"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AgentPosition(str, Enum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    NEUTRAL = "neutral"
    CLARIFY = "clarify"
    UNKNOWN = "unknown"


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================
# Constants
# ============================================================

DEFAULT_AGENTS = ("chatgpt", "grok", "hark")

CONSENSUS_FILE_PREFIX = "consensus_"
CONSENSUS_FILE_SUFFIX = ".json"

DEFAULT_CONSENSUS_THRESHOLD = 0.67
DEFAULT_EVIDENCE_THRESHOLD = 0.50

MAX_CONSENSUS_THRESHOLD = 1.0
MIN_CONSENSUS_THRESHOLD = 0.0

VALID_CONCLUSIONS = frozenset(
    item.value for item in ConsensusStatus
)


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


def _json_safe(value: Any) -> Any:
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

    # Plain objects (SimpleNamespace 等) 按属性转成映射，
    # 不能直接 str()，否则嵌套的 rounds/messages 会丢失。
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return _json_safe(vars(value))

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
    if not isinstance(agent_id, str):
        raise ValueError("agent_id must be a string.")

    agent_id = agent_id.strip().lower()

    if agent_id not in DEFAULT_AGENTS:
        raise ValueError(
            f"Unsupported agent_id: {agent_id}"
        )

    return agent_id


def _clamp_score(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        score = float(value)
    except (TypeError, ValueError):
        return None

    if score != score:
        return None

    return max(0.0, min(1.0, score))


def _normalize_position(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value

    if not isinstance(value, str):
        return AgentPosition.UNKNOWN.value

    normalized = value.strip().lower()

    valid = {
        item.value for item in AgentPosition
    }

    if normalized not in valid:
        return AgentPosition.UNKNOWN.value

    return normalized


# ============================================================
# Data models
# ============================================================

@dataclass
class AgentConsensusVote:
    agent_id: str
    position: str
    response_count: int = 0
    evidence_count: int = 0
    evidence_strength: str = EvidenceStrength.NONE.value
    latest_response: str = ""
    confidence_text: str = ""
    source_round: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class ConsensusIssue:
    issue_id: str
    category: str
    description: str
    severity: str = "medium"
    source: str = "cross_validation"
    positions: dict[str, str] = field(default_factory=dict)
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


@dataclass
class ConsensusReport:
    consensus_id: str
    task_id: str
    validation_id: Optional[str]
    debate_id: Optional[str]
    status: str
    confidence: str
    agreement_score: Optional[float]
    position_agreement: float
    evidence_score: float
    participants: list[str]
    votes: list[AgentConsensusVote]
    issues: list[ConsensusIssue]
    consensus_points: list[str]
    unresolved_issues: list[str]
    conclusion: str
    risk_warnings: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "consensus_id": self.consensus_id,
            "task_id": self.task_id,
            "validation_id": self.validation_id,
            "debate_id": self.debate_id,
            "status": self.status,
            "confidence": self.confidence,
            "agreement_score": self.agreement_score,
            "position_agreement": self.position_agreement,
            "evidence_score": self.evidence_score,
            "participants": list(self.participants),
            "votes": [
                vote.to_dict()
                for vote in self.votes
            ],
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
            "consensus_points": list(self.consensus_points),
            "unresolved_issues": list(self.unresolved_issues),
            "conclusion": self.conclusion,
            "risk_warnings": list(self.risk_warnings),
            "metadata": _json_safe(self.metadata),
            "created_at": self.created_at,
        }


@dataclass
class ConsensusSummary:
    consensus_id: str
    task_id: str
    status: str
    confidence: str
    participant_count: int
    position_agreement: float
    evidence_score: float
    issue_count: int
    unresolved_issue_count: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


# ============================================================
# Consensus engine
# ============================================================

class ConsensusEngine:
    """
    Deterministic consensus engine for the AI research team.

    Inputs:
    - Step 4 CrossValidator result or exported payload.
    - Optional Step 5 DebateSession or debate_id.

    Outputs:
    - Agent positions and evidence summaries.
    - Position agreement and evidence scores.
    - Consensus status and unresolved issues.
    - Persisted JSON consensus report.

    This module does not call model APIs and does not execute trades.
    """

    def __init__(
        self,
        task_manager: Any,
        cross_validator: Any,
        debate_engine: Any = None,
        storage_dir: Optional[str | Path] = None,
        consensus_threshold: float = DEFAULT_CONSENSUS_THRESHOLD,
        evidence_threshold: float = DEFAULT_EVIDENCE_THRESHOLD,
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

        self._validate_threshold(
            consensus_threshold,
            "consensus_threshold",
        )
        self._validate_threshold(
            evidence_threshold,
            "evidence_threshold",
        )

        self.task_manager = task_manager
        self.cross_validator = cross_validator
        self.debate_engine = debate_engine
        self.consensus_threshold = float(consensus_threshold)
        self.evidence_threshold = float(evidence_threshold)

        if storage_dir is None:
            collector = getattr(
                cross_validator,
                "report_collector",
                None,
            )

            collector_dir = getattr(
                collector,
                "storage_dir",
                None,
            )

            if collector_dir is not None:
                storage_dir = (
                    Path(collector_dir) / "_consensus"
                )
            else:
                storage_dir = (
                    Path.cwd()
                    / "data"
                    / "ai_team"
                    / "consensus"
                )

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._reports: dict[str, ConsensusReport] = {}

    @staticmethod
    def _validate_threshold(
        value: Any,
        field_name: str,
    ) -> None:
        if isinstance(value, bool):
            raise ValueError(
                f"{field_name} must be a number between 0 and 1."
            )

        if not isinstance(value, (int, float)):
            raise ValueError(
                f"{field_name} must be a number between 0 and 1."
            )

        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(
                f"{field_name} must be between 0 and 1."
            )

    # --------------------------------------------------------
    # Public API: build consensus
    # --------------------------------------------------------

    def build_consensus(
        self,
        task_id: str,
        validation_result: Any = None,
        validation_id: Optional[str] = None,
        debate: Any = None,
        debate_id: Optional[str] = None,
        participants: Optional[Sequence[str]] = None,
        force: bool = False,
    ) -> ConsensusReport:
        """
        Build a consensus report from validation and optional debate.

        validation_result:
            A Step 4 result object or exported mapping.

        validation_id:
            Existing Step 4 result ID.

        debate:
            A Step 5 DebateSession or exported mapping.

        debate_id:
            Existing debate ID. Requires debate_engine.

        participants:
            Optional explicit agent list.

        force:
            Allows a report even when validation indicates no debate
            is required. It does not force a positive consensus.
        """
        task_id = _safe_identifier(task_id, "task_id")

        task = self.task_manager.get_task(task_id)

        if task is None:
            raise ConsensusTaskNotFoundError(
                f"Task not found: {task_id}"
            )

        validation_payload = self._resolve_validation(
            task_id=task_id,
            validation_result=validation_result,
            validation_id=validation_id,
        )

        payload_task_id = validation_payload.get("task_id")

        if payload_task_id and payload_task_id != task_id:
            raise ConsensusValidationError(
                "Validation task_id does not match requested task_id."
            )

        if (
            not force
            and validation_payload.get("requires_debate") is True
            and debate is None
            and debate_id is None
        ):
            raise ConsensusDebateError(
                "Validation requires debate, but no debate result "
                "was supplied."
            )

        resolved_debate = self._resolve_debate(
            debate=debate,
            debate_id=debate_id,
        )

        resolved_participants = self._resolve_participants(
            validation_payload,
            resolved_debate,
            participants,
        )

        votes = self._build_votes(
            participants=resolved_participants,
            debate=resolved_debate,
        )

        position_agreement = self._calculate_position_agreement(
            votes
        )

        evidence_score = self._calculate_evidence_score(
            votes
        )

        agreement_score = _clamp_score(
            validation_payload.get("agreement_score")
        )

        issues = self._build_issues(
            validation_payload,
            resolved_debate,
            votes,
        )

        consensus_points = self._build_consensus_points(
            validation_payload,
            resolved_debate,
        )

        unresolved_issues = self._build_unresolved_issues(
            resolved_debate,
            issues,
        )

        status = self._determine_status(
            votes=votes,
            position_agreement=position_agreement,
            evidence_score=evidence_score,
            validation_payload=validation_payload,
            debate=resolved_debate,
            unresolved_issues=unresolved_issues,
        )

        confidence = self._determine_confidence(
            position_agreement=position_agreement,
            evidence_score=evidence_score,
            agreement_score=agreement_score,
            status=status,
        )

        risk_warnings = self._build_risk_warnings(
            status=status,
            confidence=confidence,
            votes=votes,
            issues=issues,
            unresolved_issues=unresolved_issues,
            validation_payload=validation_payload,
        )

        conclusion = self._build_conclusion(
            status=status,
            votes=votes,
            position_agreement=position_agreement,
            evidence_score=evidence_score,
            unresolved_issues=unresolved_issues,
        )

        report = ConsensusReport(
            consensus_id=_new_id("consensus"),
            task_id=task_id,
            validation_id=validation_payload.get("validation_id"),
            debate_id=(
                resolved_debate.get("debate_id")
                if resolved_debate
                else None
            ),
            status=status.value,
            confidence=confidence.value,
            agreement_score=agreement_score,
            position_agreement=position_agreement,
            evidence_score=evidence_score,
            participants=list(resolved_participants),
            votes=votes,
            issues=issues,
            consensus_points=consensus_points,
            unresolved_issues=unresolved_issues,
            conclusion=conclusion,
            risk_warnings=risk_warnings,
            metadata={
                "task_title": _get_value(task, "title", ""),
                "task_status": _json_safe(
                    _get_value(task, "status")
                ),
                "validation_requires_debate": bool(
                    validation_payload.get("requires_debate", False)
                ),
                "debate_status": (
                    resolved_debate.get("status")
                    if resolved_debate
                    else None
                ),
                "debate_conclusion": (
                    resolved_debate.get("conclusion")
                    if resolved_debate
                    else None
                ),
                "consensus_threshold": self.consensus_threshold,
                "evidence_threshold": self.evidence_threshold,
                "calculation_method": (
                    "deterministic_position_and_evidence_rules"
                ),
            },
        )

        self.save_report(report)
        return report

    # --------------------------------------------------------
    # Resolve Step 4 validation input
    # --------------------------------------------------------

    def _resolve_validation(
        self,
        task_id: str,
        validation_result: Any,
        validation_id: Optional[str],
    ) -> dict[str, Any]:
        if validation_result is None:
            if validation_id is not None:
                validation_id = _safe_identifier(
                    validation_id,
                    "validation_id",
                )

                try:
                    validation_result = (
                        self.cross_validator.get_result(validation_id)
                    )
                except Exception as exc:
                    raise ConsensusValidationError(
                        f"Could not load validation result: {exc}"
                    ) from exc
            else:
                try:
                    validation_result = (
                        self.cross_validator.validate_task(task_id)
                    )
                except Exception as exc:
                    raise ConsensusValidationError(
                        f"Could not validate task: {exc}"
                    ) from exc

        if isinstance(validation_result, Mapping):
            payload = dict(validation_result)
        else:
            try:
                payload = (
                    self.cross_validator.export_debate_payload(
                        validation_result
                    )
                )
            except Exception as exc:
                raise ConsensusValidationError(
                    f"Could not export validation payload: {exc}"
                ) from exc

        if not isinstance(payload, Mapping):
            raise ConsensusValidationError(
                "Validation payload must be a mapping."
            )

        payload = _json_safe(dict(payload))

        payload.setdefault(
            "validation_id",
            _get_value(validation_result, "validation_id"),
        )
        payload.setdefault("task_id", task_id)
        payload.setdefault("conflicts", [])
        payload.setdefault("consensus", [])
        payload.setdefault("agent_analyses", [])
        payload.setdefault("agreement_score", None)
        payload.setdefault("requires_debate", False)

        for key in (
            "conflicts",
            "consensus",
            "agent_analyses",
        ):
            if not isinstance(payload[key], list):
                raise ConsensusValidationError(
                    f"Validation field '{key}' must be a list."
                )

        return payload

    # --------------------------------------------------------
    # Resolve Step 5 debate input
    # --------------------------------------------------------

    def _resolve_debate(
        self,
        debate: Any,
        debate_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        if debate is not None and debate_id is not None:
            raise ConsensusDebateError(
                "Provide debate or debate_id, not both."
            )

        if debate_id is not None:
            debate_id = _safe_identifier(
                debate_id,
                "debate_id",
            )

            if self.debate_engine is None:
                raise ConsensusDebateError(
                    "debate_engine is required when using debate_id."
                )

            try:
                debate = self.debate_engine.get_debate(debate_id)
            except Exception as exc:
                raise ConsensusDebateError(
                    f"Could not load debate: {exc}"
                ) from exc

        if debate is None:
            return None

        if isinstance(debate, Mapping):
            data = dict(debate)
        elif hasattr(debate, "to_dict"):
            data = debate.to_dict()
        else:
            try:
                data = {
                    "debate_id": _get_value(debate, "debate_id"),
                    "task_id": _get_value(debate, "task_id"),
                    "status": _get_value(debate, "status"),
                    "participants": _get_value(
                        debate,
                        "participants",
                        [],
                    ),
                    "rounds": _get_value(
                        debate,
                        "rounds",
                        [],
                    ),
                    "conclusion": _get_value(
                        debate,
                        "conclusion",
                    ),
                    "conclusion_text": _get_value(
                        debate,
                        "conclusion_text",
                        "",
                    ),
                    "unresolved_issues": _get_value(
                        debate,
                        "unresolved_issues",
                        [],
                    ),
                }
            except Exception as exc:
                raise ConsensusDebateError(
                    f"Unsupported debate object: {exc}"
                ) from exc

        data = _json_safe(data)

        if not isinstance(data.get("rounds", []), list):
            raise ConsensusDebateError(
                "Debate rounds must be a list."
            )

        if not isinstance(
            data.get("unresolved_issues", []),
            list,
        ):
            raise ConsensusDebateError(
                "Debate unresolved_issues must be a list."
            )

        return data

    # --------------------------------------------------------
    # Resolve participants
    # --------------------------------------------------------

    def _resolve_participants(
        self,
        validation_payload: Mapping[str, Any],
        debate: Optional[Mapping[str, Any]],
        participants: Optional[Sequence[str]],
    ) -> list[str]:
        if participants is not None:
            candidates = list(participants)
        else:
            candidates = []

            if debate:
                candidates.extend(
                    debate.get("participants", [])
                )

            if not candidates:
                for analysis in validation_payload.get(
                    "agent_analyses",
                    [],
                ):
                    agent_id = _get_value(
                        analysis,
                        "agent_id",
                    )

                    if agent_id:
                        candidates.append(agent_id)

            if not candidates:
                candidates = list(DEFAULT_AGENTS)

        result: list[str] = []

        for candidate in candidates:
            try:
                agent_id = _normalize_agent_id(candidate)
            except ValueError as exc:
                raise ConsensusValidationError(
                    str(exc)
                ) from exc

            if agent_id not in result:
                result.append(agent_id)

        if not result:
            raise ConsensusValidationError(
                "At least one participant is required."
            )

        return result

    # --------------------------------------------------------
    # Build votes from the latest debate round
    # --------------------------------------------------------

    def _latest_messages_by_agent(
        self,
        debate: Optional[Mapping[str, Any]],
    ) -> dict[str, Mapping[str, Any]]:
        if not debate:
            return {}

        rounds = debate.get("rounds", [])

        ordered_rounds = sorted(
            rounds,
            key=lambda item: int(
                _get_value(item, "round_number", 0)
            ),
        )

        latest: dict[str, Mapping[str, Any]] = {}

        for debate_round in ordered_rounds:
            messages = _get_value(
                debate_round,
                "messages",
                [],
            )

            if not isinstance(messages, list):
                continue

            for message in messages:
                agent_id = _get_value(
                    message,
                    "agent_id",
                )

                if not agent_id:
                    continue

                try:
                    normalized = _normalize_agent_id(agent_id)
                except ValueError:
                    continue

                latest[normalized] = message

        return latest

    def _build_votes(
        self,
        participants: Sequence[str],
        debate: Optional[Mapping[str, Any]],
    ) -> list[AgentConsensusVote]:
        latest_messages = self._latest_messages_by_agent(
            debate
        )

        response_counts: dict[str, int] = {}
        evidence_counts: dict[str, int] = {}

        if debate:
            for debate_round in debate.get("rounds", []):
                for message in _get_value(
                    debate_round,
                    "messages",
                    [],
                ):
                    agent_id = _get_value(
                        message,
                        "agent_id",
                    )

                    try:
                        agent_id = _normalize_agent_id(agent_id)
                    except (ValueError, TypeError):
                        continue

                    response_counts[agent_id] = (
                        response_counts.get(agent_id, 0) + 1
                    )

                    evidence = _get_value(
                        message,
                        "evidence",
                        [],
                    )

                    if isinstance(evidence, list):
                        evidence_counts[agent_id] = (
                            evidence_counts.get(agent_id, 0)
                            + len([
                                item
                                for item in evidence
                                if isinstance(item, str)
                                and item.strip()
                            ])
                        )

        votes: list[AgentConsensusVote] = []

        for agent_id in participants:
            message = latest_messages.get(agent_id)

            if message is None:
                votes.append(
                    AgentConsensusVote(
                        agent_id=agent_id,
                        position=AgentPosition.UNKNOWN.value,
                        response_count=response_counts.get(
                            agent_id,
                            0,
                        ),
                        evidence_count=evidence_counts.get(
                            agent_id,
                            0,
                        ),
                    )
                )
                continue

            position = _normalize_position(
                _get_value(message, "position")
            )

            evidence_count = evidence_counts.get(
                agent_id,
                0,
            )

            strength = self._evidence_strength(
                evidence_count
            )

            content = _get_value(
                message,
                "content",
                "",
            )

            if not isinstance(content, str):
                content = str(content)

            round_number = _get_value(
                message,
                "round_number",
            )

            confidence_text = self._extract_confidence(
                content
            )

            votes.append(
                AgentConsensusVote(
                    agent_id=agent_id,
                    position=position,
                    response_count=response_counts.get(
                        agent_id,
                        0,
                    ),
                    evidence_count=evidence_count,
                    evidence_strength=strength.value,
                    latest_response=content,
                    confidence_text=confidence_text,
                    source_round=(
                        int(round_number)
                        if round_number is not None
                        else None
                    ),
                )
            )

        return votes

    @staticmethod
    def _extract_confidence(content: str) -> str:
        match = re.search(
            r"CONFIDENCE\s*:\s*(low|medium|high)",
            content,
            flags=re.IGNORECASE,
        )

        if not match:
            return ""

        return match.group(1).lower()

    @staticmethod
    def _evidence_strength(
        evidence_count: int,
    ) -> EvidenceStrength:
        if evidence_count >= 3:
            return EvidenceStrength.STRONG

        if evidence_count >= 1:
            return EvidenceStrength.MODERATE

        return EvidenceStrength.NONE


    # --------------------------------------------------------
    # Calculate agreement and evidence
    # --------------------------------------------------------

    @staticmethod
    def _calculate_position_agreement(
        votes: Sequence[AgentConsensusVote],
    ) -> float:
        if not votes:
            return 0.0

        known_positions = [
            vote.position
            for vote in votes
            if vote.position in {
                AgentPosition.SUPPORT.value,
                AgentPosition.OPPOSE.value,
                AgentPosition.NEUTRAL.value,
            }
        ]

        if not known_positions:
            return 0.0

        counts: dict[str, int] = {}

        for position in known_positions:
            counts[position] = counts.get(position, 0) + 1

        largest_group = max(counts.values())

        # Missing/unknown participants count against agreement.
        return largest_group / len(votes)

    @staticmethod
    def _calculate_evidence_score(
        votes: Sequence[AgentConsensusVote],
    ) -> float:
        if not votes:
            return 0.0

        supported = sum(
            1
            for vote in votes
            if vote.evidence_count > 0
        )

        return supported / len(votes)

    # --------------------------------------------------------
    # Build issues and consensus points
    # --------------------------------------------------------

    def _build_issues(
        self,
        validation_payload: Mapping[str, Any],
        debate: Optional[Mapping[str, Any]],
        votes: Sequence[AgentConsensusVote],
    ) -> list[ConsensusIssue]:
        issues: list[ConsensusIssue] = []

        for index, conflict in enumerate(
            validation_payload.get("conflicts", []),
            start=1,
        ):
            description = self._describe_item(conflict)

            if not description:
                continue

            severity = _get_value(
                conflict,
                "severity",
                "medium",
            )

            category = _get_value(
                conflict,
                "category",
                "general",
            )

            issues.append(
                ConsensusIssue(
                    issue_id=f"validation_conflict_{index}",
                    category=str(category),
                    description=description,
                    severity=str(severity),
                    source="cross_validation",
                    positions=self._positions_for_issue(
                        conflict,
                        votes,
                    ),
                    resolved=False,
                )
            )

        if debate:
            unresolved = debate.get(
                "unresolved_issues",
                [],
            )

            for index, item in enumerate(
                unresolved,
                start=1,
            ):
                description = self._describe_item(item)

                if not description:
                    continue

                issues.append(
                    ConsensusIssue(
                        issue_id=f"debate_unresolved_{index}",
                        category="unresolved",
                        description=description,
                        severity="medium",
                        source="debate",
                        resolved=False,
                    )
                )

        return issues

    @staticmethod
    def _positions_for_issue(
        conflict: Any,
        votes: Sequence[AgentConsensusVote],
    ) -> dict[str, str]:
        positions = _get_value(
            conflict,
            "positions",
            {},
        )

        if isinstance(positions, Mapping):
            result: dict[str, str] = {}

            for agent_id, position in positions.items():
                try:
                    normalized_agent = _normalize_agent_id(
                        agent_id
                    )
                except ValueError:
                    continue

                result[normalized_agent] = _normalize_position(
                    position
                )

            if result:
                return result

        return {
            vote.agent_id: vote.position
            for vote in votes
            if vote.position != AgentPosition.UNKNOWN.value
        }

    @staticmethod
    def _describe_item(item: Any) -> str:
        if isinstance(item, str):
            return item.strip()

        if isinstance(item, Mapping):
            for key in (
                "description",
                "claim_text",
                "claim",
                "summary",
                "reason",
                "text",
            ):
                value = item.get(key)

                if isinstance(value, str) and value.strip():
                    return value.strip()

            return json.dumps(
                _json_safe(item),
                ensure_ascii=False,
                sort_keys=True,
            )

        if item is None:
            return ""

        return str(item).strip()

    def _build_consensus_points(
        self,
        validation_payload: Mapping[str, Any],
        debate: Optional[Mapping[str, Any]],
    ) -> list[str]:
        points: list[str] = []

        for item in validation_payload.get("consensus", []):
            description = self._describe_item(item)

            if description and description not in points:
                points.append(description)

        if debate:
            debate_consensus = debate.get(
                "consensus_points",
                [],
            )

            if isinstance(debate_consensus, list):
                for item in debate_consensus:
                    description = self._describe_item(item)

                    if description and description not in points:
                        points.append(description)

        return points

    def _build_unresolved_issues(
        self,
        debate: Optional[Mapping[str, Any]],
        issues: Sequence[ConsensusIssue],
    ) -> list[str]:
        unresolved: list[str] = []

        if debate:
            for item in debate.get("unresolved_issues", []):
                description = self._describe_item(item)

                if description and description not in unresolved:
                    unresolved.append(description)

        for issue in issues:
            if not issue.resolved:
                if issue.description not in unresolved:
                    unresolved.append(issue.description)

        return unresolved

    # --------------------------------------------------------
    # Determine consensus status
    # --------------------------------------------------------

    def _determine_status(
        self,
        votes: Sequence[AgentConsensusVote],
        position_agreement: float,
        evidence_score: float,
        validation_payload: Mapping[str, Any],
        debate: Optional[Mapping[str, Any]],
        unresolved_issues: Sequence[str],
    ) -> ConsensusStatus:
        if not votes:
            return ConsensusStatus.INSUFFICIENT_EVIDENCE

        known_votes = [
            vote
            for vote in votes
            if vote.position in {
                AgentPosition.SUPPORT.value,
                AgentPosition.OPPOSE.value,
                AgentPosition.NEUTRAL.value,
            }
        ]

        if not known_votes:
            return ConsensusStatus.INSUFFICIENT_EVIDENCE

        if evidence_score < self.evidence_threshold:
            return ConsensusStatus.INSUFFICIENT_EVIDENCE

        if position_agreement >= self.consensus_threshold:
            if unresolved_issues:
                return ConsensusStatus.PARTIAL_CONSENSUS

            return ConsensusStatus.CONSENSUS

        # 低于阈值即视为立场未统一，不能因为过半就升级为
        # partial_consensus —— 只有 debate 结论明确说明部分一致时才采纳。
        debate_conclusion = None

        if debate:
            debate_conclusion = debate.get("conclusion")

        if debate_conclusion == ConsensusStatus.INSUFFICIENT_EVIDENCE.value:
            return ConsensusStatus.INSUFFICIENT_EVIDENCE

        if debate_conclusion == ConsensusStatus.PARTIAL_CONSENSUS.value:
            return ConsensusStatus.PARTIAL_CONSENSUS

        if debate_conclusion == ConsensusStatus.CONSENSUS.value:
            # Do not promote a disagreement into consensus.
            return ConsensusStatus.NO_CONSENSUS

        return ConsensusStatus.NO_CONSENSUS

    # --------------------------------------------------------
    # Determine confidence
    # --------------------------------------------------------

    @staticmethod
    def _determine_confidence(
        position_agreement: float,
        evidence_score: float,
        agreement_score: Optional[float],
        status: ConsensusStatus,
    ) -> ConfidenceLevel:
        if status == ConsensusStatus.INSUFFICIENT_EVIDENCE:
            return ConfidenceLevel.LOW

        scores = [
            position_agreement,
            evidence_score,
        ]

        if agreement_score is not None:
            scores.append(agreement_score)

        average_score = sum(scores) / len(scores)

        if (
            average_score >= 0.80
            and position_agreement >= 0.80
            and evidence_score >= 0.67
            and status == ConsensusStatus.CONSENSUS
        ):
            return ConfidenceLevel.HIGH

        if average_score >= 0.55:
            return ConfidenceLevel.MEDIUM

        return ConfidenceLevel.LOW

    # --------------------------------------------------------
    # Risk warnings and conclusion
    # --------------------------------------------------------

    @staticmethod
    def _build_risk_warnings(
        status: ConsensusStatus,
        confidence: ConfidenceLevel,
        votes: Sequence[AgentConsensusVote],
        issues: Sequence[ConsensusIssue],
        unresolved_issues: Sequence[str],
        validation_payload: Mapping[str, Any],
    ) -> list[str]:
        warnings: list[str] = []

        if status == ConsensusStatus.INSUFFICIENT_EVIDENCE:
            warnings.append(
                "证据不足：当前材料不足以支持可靠的团队结论。"
            )

        if status == ConsensusStatus.NO_CONSENSUS:
            warnings.append(
                "团队未形成共识：不同 Agent 的核心观点存在明显分歧。"
            )

        if status == ConsensusStatus.PARTIAL_CONSENSUS:
            warnings.append(
                "仅形成部分共识：仍有观点分歧或未解决事项。"
            )

        if confidence == ConfidenceLevel.LOW:
            warnings.append(
                "结论置信度较低，不应将其视为已验证事实。"
            )

        missing_agents = [
            vote.agent_id
            for vote in votes
            if vote.position == AgentPosition.UNKNOWN.value
        ]

        if missing_agents:
            warnings.append(
                "以下 Agent 未提交有效立场："
                + ", ".join(missing_agents)
            )

        no_evidence_agents = [
            vote.agent_id
            for vote in votes
            if vote.evidence_count == 0
        ]

        if no_evidence_agents:
            warnings.append(
                "以下 Agent 未提供证据引用："
                + ", ".join(no_evidence_agents)
            )

        if issues:
            warnings.append(
                f"交叉验证识别出 {len(issues)} 项待核查分歧。"
            )

        if unresolved_issues:
            warnings.append(
                f"仍有 {len(unresolved_issues)} 项未解决问题。"
            )

        if validation_payload.get("requires_debate"):
            warnings.append(
                "交叉验证曾标记需要辩论；最终结论仍需结合原始证据复核。"
            )

        return list(dict.fromkeys(warnings))

    @staticmethod
    def _build_conclusion(
        status: ConsensusStatus,
        votes: Sequence[AgentConsensusVote],
        position_agreement: float,
        evidence_score: float,
        unresolved_issues: Sequence[str],
    ) -> str:
        position_counts: dict[str, int] = {}

        for vote in votes:
            if vote.position == AgentPosition.UNKNOWN.value:
                continue

            position_counts[vote.position] = (
                position_counts.get(vote.position, 0) + 1
            )

        position_summary = (
            "、".join(
                f"{position}: {count}"
                for position, count in sorted(
                    position_counts.items()
                )
            )
            if position_counts
            else "暂无有效立场"
        )

        status_text = {
            ConsensusStatus.CONSENSUS:
                "团队形成共识",
            ConsensusStatus.PARTIAL_CONSENSUS:
                "团队形成部分共识",
            ConsensusStatus.NO_CONSENSUS:
                "团队未形成共识",
            ConsensusStatus.INSUFFICIENT_EVIDENCE:
                "当前证据不足，无法形成可靠共识",
        }[status]

        return (
            f"{status_text}。"
            f"立场分布：{position_summary}。"
            f"立场一致性：{position_agreement:.2%}；"
            f"证据覆盖率：{evidence_score:.2%}。"
            f"未解决问题：{len(unresolved_issues)} 项。"
            "本结论是规则计算形成的研究协作结果，"
            "不代表对相关事实或证券价格的独立验证。"
        )

    # --------------------------------------------------------
    # Public API: report retrieval
    # --------------------------------------------------------

    def get_report(
        self,
        consensus_id: str,
    ) -> ConsensusReport:
        consensus_id = _safe_identifier(
            consensus_id,
            "consensus_id",
        )

        if consensus_id in self._reports:
            return self._reports[consensus_id]

        path = self._report_path(consensus_id)

        if not path.exists():
            raise ConsensusNotFoundError(
                f"Consensus report not found: {consensus_id}"
            )

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            report = self._report_from_dict(data)
            self._reports[report.consensus_id] = report

            return report

        except ConsensusEngineError:
            raise
        except Exception as exc:
            raise ConsensusPersistenceError(
                f"Could not load consensus report: {exc}"
            ) from exc

    def list_reports(
        self,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[ConsensusSummary]:
        normalized_task_id = None

        if task_id is not None:
            normalized_task_id = _safe_identifier(
                task_id,
                "task_id",
            )

        normalized_status = None

        if status is not None:
            normalized_status = _safe_text(
                status,
                "status",
            ).lower()

            if normalized_status not in VALID_CONCLUSIONS:
                raise ValueError(
                    "Invalid consensus status."
                )

        reports: dict[str, ConsensusReport] = dict(
            self._reports
        )

        for path in self.storage_dir.glob(
            f"{CONSENSUS_FILE_PREFIX}*{CONSENSUS_FILE_SUFFIX}"
        ):
            consensus_id = path.stem[
                len(CONSENSUS_FILE_PREFIX):
            ]

            if consensus_id in reports:
                continue

            try:
                report = self.get_report(consensus_id)
                reports[report.consensus_id] = report
            except ConsensusEngineError:
                continue

        summaries: list[ConsensusSummary] = []

        for report in reports.values():
            if (
                normalized_task_id is not None
                and report.task_id != normalized_task_id
            ):
                continue

            if (
                normalized_status is not None
                and report.status != normalized_status
            ):
                continue

            summaries.append(
                self._build_summary(report)
            )

        summaries.sort(
            key=lambda item: item.created_at,
            reverse=True,
        )

        return summaries

    @staticmethod
    def _build_summary(
        report: ConsensusReport,
    ) -> ConsensusSummary:
        return ConsensusSummary(
            consensus_id=report.consensus_id,
            task_id=report.task_id,
            status=report.status,
            confidence=report.confidence,
            participant_count=len(report.participants),
            position_agreement=report.position_agreement,
            evidence_score=report.evidence_score,
            issue_count=len(report.issues),
            unresolved_issue_count=len(
                report.unresolved_issues
            ),
            created_at=report.created_at,
        )

    # --------------------------------------------------------
    # Public API: export
    # --------------------------------------------------------

    def export_report(
        self,
        consensus_id: str,
    ) -> dict[str, Any]:
        return self.get_report(consensus_id).to_dict()

    def export_markdown(
        self,
        consensus_id: str,
    ) -> str:
        report = self.get_report(consensus_id)

        lines = [
            "# AI Team Consensus Report",
            "",
            f"- Consensus ID: {report.consensus_id}",
            f"- Task ID: {report.task_id}",
            f"- Validation ID: {report.validation_id or 'N/A'}",
            f"- Debate ID: {report.debate_id or 'N/A'}",
            f"- Status: {report.status}",
            f"- Confidence: {report.confidence}",
            f"- Participants: {', '.join(report.participants)}",
            "",
            "## Scores",
            "",
            f"- Cross-validation agreement: "
            f"{self._format_score(report.agreement_score)}",
            f"- Position agreement: "
            f"{report.position_agreement:.2%}",
            f"- Evidence coverage: "
            f"{report.evidence_score:.2%}",
            "",
            "## Agent positions",
            "",
        ]

        for vote in report.votes:
            lines.extend([
                f"### {vote.agent_id}",
                "",
                f"- Position: {vote.position}",
                f"- Responses: {vote.response_count}",
                f"- Evidence count: {vote.evidence_count}",
                f"- Evidence strength: {vote.evidence_strength}",
                "",
            ])

            if vote.latest_response:
                lines.extend([
                    vote.latest_response,
                    "",
                ])

        lines.extend([
            "## Consensus points",
            "",
        ])

        if report.consensus_points:
            for point in report.consensus_points:
                lines.append(f"- {point}")
        else:
            lines.append("No explicit consensus points recorded.")

        lines.extend([
            "",
            "## Disputed issues",
            "",
        ])

        if report.issues:
            for issue in report.issues:
                lines.append(
                    f"- [{issue.severity}] {issue.description}"
                )
        else:
            lines.append("No disputed issues recorded.")

        lines.extend([
            "",
            "## Unresolved issues",
            "",
        ])

        if report.unresolved_issues:
            for issue in report.unresolved_issues:
                lines.append(f"- {issue}")
        else:
            lines.append("None recorded.")

        lines.extend([
            "",
            "## Risk warnings",
            "",
        ])

        if report.risk_warnings:
            for warning in report.risk_warnings:
                lines.append(f"- {warning}")
        else:
            lines.append("No warnings recorded.")

        lines.extend([
            "",
            "## Final conclusion",
            "",
            report.conclusion,
            "",
            "## Methodology note",
            "",
            "This report is generated by deterministic rules. "
            "It does not independently verify the truth of cited "
            "evidence and is not an investment recommendation.",
            "",
        ])

        return "\n".join(lines)

    @staticmethod
    def _format_score(score: Optional[float]) -> str:
        if score is None:
            return "N/A"

        return f"{score:.2%}"

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def save_report(
        self,
        report: ConsensusReport,
    ) -> Path:
        if not isinstance(report, ConsensusReport):
            raise TypeError(
                "report must be a ConsensusReport."
            )

        path = self._report_path(report.consensus_id)

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
                    report.to_dict(),
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            temporary_path.replace(path)
            self._reports[report.consensus_id] = report

            return path

        except Exception as exc:
            raise ConsensusPersistenceError(
                f"Could not save consensus report: {exc}"
            ) from exc

    def _report_path(self, consensus_id: str) -> Path:
        consensus_id = _safe_identifier(
            consensus_id,
            "consensus_id",
        )

        # consensus_id 自带 "consensus_" 前缀，落盘时只保留一次。
        if consensus_id.startswith(CONSENSUS_FILE_PREFIX):
            consensus_id = consensus_id[len(CONSENSUS_FILE_PREFIX):]

        return self.storage_dir / (
            f"{CONSENSUS_FILE_PREFIX}{consensus_id}"
            f"{CONSENSUS_FILE_SUFFIX}"
        )

    @staticmethod
    def _report_from_dict(
        data: Mapping[str, Any],
    ) -> ConsensusReport:
        try:
            votes = [
                AgentConsensusVote(
                    agent_id=item["agent_id"],
                    position=item["position"],
                    response_count=int(
                        item.get("response_count", 0)
                    ),
                    evidence_count=int(
                        item.get("evidence_count", 0)
                    ),
                    evidence_strength=item.get(
                        "evidence_strength",
                        EvidenceStrength.NONE.value,
                    ),
                    latest_response=item.get(
                        "latest_response",
                        "",
                    ),
                    confidence_text=item.get(
                        "confidence_text",
                        "",
                    ),
                    source_round=item.get("source_round"),
                )
                for item in data.get("votes", [])
            ]

            issues = [
                ConsensusIssue(
                    issue_id=item["issue_id"],
                    category=item["category"],
                    description=item["description"],
                    severity=item.get("severity", "medium"),
                    source=item.get(
                        "source",
                        "cross_validation",
                    ),
                    positions=dict(item.get("positions", {})),
                    resolved=bool(item.get("resolved", False)),
                )
                for item in data.get("issues", [])
            ]

            report = ConsensusReport(
                consensus_id=data["consensus_id"],
                task_id=data["task_id"],
                validation_id=data.get("validation_id"),
                debate_id=data.get("debate_id"),
                status=data["status"],
                confidence=data["confidence"],
                agreement_score=data.get("agreement_score"),
                position_agreement=float(
                    data["position_agreement"]
                ),
                evidence_score=float(data["evidence_score"]),
                participants=list(data["participants"]),
                votes=votes,
                issues=issues,
                consensus_points=list(
                    data.get("consensus_points", [])
                ),
                unresolved_issues=list(
                    data.get("unresolved_issues", [])
                ),
                conclusion=data["conclusion"],
                risk_warnings=list(
                    data.get("risk_warnings", [])
                ),
                metadata=dict(data.get("metadata", {})),
                created_at=data.get(
                    "created_at",
                    _utc_now(),
                ),
            )

            if report.status not in VALID_CONCLUSIONS:
                raise ValueError("Invalid persisted status.")

            return report

        except Exception as exc:
            raise ConsensusPersistenceError(
                f"Invalid persisted consensus data: {exc}"
            ) from exc
