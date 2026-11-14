# ai_team/investment_committee.py

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


# ============================================================
# Exceptions
# ============================================================

class InvestmentCommitteeError(Exception):
    """Base exception for investment committee errors."""


class CommitteeTaskNotFoundError(InvestmentCommitteeError):
    """Raised when the requested task does not exist."""


class CommitteeConsensusError(InvestmentCommitteeError):
    """Raised when the consensus report is missing or invalid."""


class CommitteeValidationError(InvestmentCommitteeError):
    """Raised when committee input is invalid."""


class CommitteeNotFoundError(InvestmentCommitteeError):
    """Raised when a committee decision cannot be found."""


class CommitteePersistenceError(InvestmentCommitteeError):
    """Raised when persistence or export fails."""


# ============================================================
# Enums
# ============================================================

class CommitteeStatus(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CommitteeVote(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_CONDITIONS = "approve_with_conditions"
    REJECT = "reject"
    ABSTAIN = "abstain"


class CommitteeRole(str, Enum):
    CHIEF_INVESTMENT_OFFICER = "cio"
    RISK_OFFICER = "risk_officer"
    QUANT_ANALYST = "quant_analyst"
    FUNDAMENTAL_ANALYST = "fundamental_analyst"
    INDUSTRY_ANALYST = "industry_analyst"
    PORTFOLIO_MANAGER = "portfolio_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
    OBSERVER = "observer"


# ============================================================
# Data models
# ============================================================

@dataclass(frozen=True)
class CommitteeMember:
    member_id: str
    name: str
    role: CommitteeRole
    weight: float = 1.0
    required: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.member_id or not self.member_id.strip():
            raise CommitteeValidationError("member_id cannot be empty")
        if not self.name or not self.name.strip():
            raise CommitteeValidationError("member name cannot be empty")
        if not isinstance(self.role, CommitteeRole):
            raise CommitteeValidationError("role must be CommitteeRole")
        if isinstance(self.weight, bool) or not isinstance(
            self.weight, (int, float)
        ):
            raise CommitteeValidationError("weight must be numeric")
        if self.weight <= 0:
            raise CommitteeValidationError("weight must be greater than zero")


@dataclass(frozen=True)
class CommitteeBallot:
    member_id: str
    vote: CommitteeVote
    rationale: str = ""
    conditions: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not self.member_id or not self.member_id.strip():
            raise CommitteeValidationError("ballot member_id cannot be empty")
        if not isinstance(self.vote, CommitteeVote):
            raise CommitteeValidationError("vote must be CommitteeVote")
        if not isinstance(self.conditions, tuple):
            raise CommitteeValidationError("conditions must be a tuple")
        if not isinstance(self.risk_flags, tuple):
            raise CommitteeValidationError("risk_flags must be a tuple")


@dataclass
class CommitteeDecision:
    decision_id: str
    task_id: str
    consensus_id: str
    status: CommitteeStatus
    members: list[CommitteeMember]
    ballots: list[CommitteeBallot]
    approval_score: float
    participation_rate: float
    quorum_met: bool
    required_members_met: bool
    conditions: list[str]
    risk_flags: list[str]
    rationale: str
    recommendation: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CommitteeDecision":
        if not isinstance(data, Mapping):
            raise CommitteeValidationError("decision data must be a mapping")

        try:
            members = [
                CommitteeMember(
                    member_id=item["member_id"],
                    name=item["name"],
                    role=CommitteeRole(item["role"]),
                    weight=float(item.get("weight", 1.0)),
                    required=bool(item.get("required", False)),
                    enabled=bool(item.get("enabled", True)),
                )
                for item in data["members"]
            ]

            ballots = [
                CommitteeBallot(
                    member_id=item["member_id"],
                    vote=CommitteeVote(item["vote"]),
                    rationale=item.get("rationale", ""),
                    conditions=tuple(item.get("conditions", [])),
                    risk_flags=tuple(item.get("risk_flags", [])),
                    created_at=item.get("created_at", ""),
                )
                for item in data["ballots"]
            ]

            return cls(
                decision_id=str(data["decision_id"]),
                task_id=str(data["task_id"]),
                consensus_id=str(data["consensus_id"]),
                status=CommitteeStatus(data["status"]),
                members=members,
                ballots=ballots,
                approval_score=float(data["approval_score"]),
                participation_rate=float(data["participation_rate"]),
                quorum_met=bool(data["quorum_met"]),
                required_members_met=bool(data["required_members_met"]),
                conditions=list(data.get("conditions", [])),
                risk_flags=list(data.get("risk_flags", [])),
                rationale=str(data.get("rationale", "")),
                recommendation=str(data.get("recommendation", "")),
                metadata=dict(data.get("metadata", {})),
                created_at=str(data.get("created_at", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CommitteeValidationError(
                f"invalid committee decision data: {exc}"
            ) from exc


# ============================================================
# Default committee
# ============================================================

def get_default_committee() -> list[CommitteeMember]:
    """Return a default committee configuration."""

    return [
        CommitteeMember(
            member_id="cio",
            name="Chief Investment Officer",
            role=CommitteeRole.CHIEF_INVESTMENT_OFFICER,
            weight=1.5,
            required=True,
        ),
        CommitteeMember(
            member_id="risk",
            name="Risk Officer",
            role=CommitteeRole.RISK_OFFICER,
            weight=1.5,
            required=True,
        ),
        CommitteeMember(
            member_id="quant",
            name="Quant Analyst",
            role=CommitteeRole.QUANT_ANALYST,
            weight=1.0,
        ),
        CommitteeMember(
            member_id="fundamental",
            name="Fundamental Analyst",
            role=CommitteeRole.FUNDAMENTAL_ANALYST,
            weight=1.0,
        ),
        CommitteeMember(
            member_id="industry",
            name="Industry Analyst",
            role=CommitteeRole.INDUSTRY_ANALYST,
            weight=1.0,
        ),
        CommitteeMember(
            member_id="compliance",
            name="Compliance Officer",
            role=CommitteeRole.COMPLIANCE_OFFICER,
            weight=1.0,
            required=True,
        ),
    ]


# ============================================================
# Serialization helpers
# ============================================================

def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _to_jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _read_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", value)
    return cleaned or "unknown"


# consensus_engine 的 ConsensusReport.confidence 是文字等级（high/medium/low），
# investment_committee 内部按 0~1 的数值校验与加权，这里做一次等级到分值的映射。
# 取值对齐 consensus_engine._determine_confidence 的判定带：
#   high  -> 平均分 ≥0.80 且一致度 ≥0.80 且证据分 ≥0.67
#   medium-> 平均分 ≥0.55
#   low   -> 其余
# 委员会 minimum_confidence 默认 0.5，因此 medium 取 0.65 留出余量，
# 避免落在一个“刚好等于阈值、只能靠严格小于比较才通过”的边界值上。
_CONFIDENCE_LEVEL_SCORES: dict[str, float] = {
    "high": 0.8,
    "medium": 0.65,
    "low": 0.3,
}

# consensus_engine.ConsensusStatus 的全部合法取值（用字面量避免循环导入）。
_KNOWN_CONSENSUS_STATUSES: set[str] = {
    "consensus",
    "partial_consensus",
    "no_consensus",
    "insufficient_evidence",
}


def _normalize_confidence(value: Any, default: float = -1.0) -> float:
    """把文字置信等级或数值统一成 0~1 的 float。"""

    if isinstance(value, str):
        key = value.strip().lower()
        if key in _CONFIDENCE_LEVEL_SCORES:
            return _CONFIDENCE_LEVEL_SCORES[key]
    result = _as_float(value, default)
    # NaN/Infinity 会让后续 < minimum_confidence 的比较大小时真时假，
    # 这里统一回落成默认值，交给上层按“非法置信度”处理。
    if not math.isfinite(result):
        return default
    return result


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result


# ============================================================
# InvestmentCommittee
# ============================================================

class InvestmentCommittee:
    """
    Governance and decision layer built on top of ConsensusEngine.

    This module produces committee decisions only. It does not place,
    route, simulate, or execute brokerage orders.
    """

    def __init__(
        self,
        task_manager: Any,
        consensus_engine: Any,
        storage_dir: Optional[str | Path] = None,
        members: Optional[Iterable[CommitteeMember]] = None,
        quorum: float = 0.60,
        approval_threshold: float = 0.67,
        minimum_confidence: float = 0.50,
        risk_veto_enabled: bool = True,
    ) -> None:
        if task_manager is None:
            raise CommitteeValidationError("task_manager is required")
        if consensus_engine is None:
            raise CommitteeValidationError("consensus_engine is required")

        for name, value in (
            ("quorum", quorum),
            ("approval_threshold", approval_threshold),
            ("minimum_confidence", minimum_confidence),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CommitteeValidationError(f"{name} must be numeric")
            if not 0.0 <= float(value) <= 1.0:
                raise CommitteeValidationError(f"{name} must be between 0 and 1")

        self.task_manager = task_manager
        self.consensus_engine = consensus_engine
        self.quorum = float(quorum)
        self.approval_threshold = float(approval_threshold)
        self.minimum_confidence = float(minimum_confidence)
        self.risk_veto_enabled = bool(risk_veto_enabled)

        if storage_dir is None:
            base_dir = getattr(consensus_engine, "storage_dir", None)
            if base_dir is None:
                base_dir = Path("data/ai_team/committee")
            else:
                base_dir = Path(base_dir).parent / "_committee"
            self.storage_dir = Path(base_dir)
        else:
            self.storage_dir = Path(storage_dir)

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.members = list(
            members if members is not None else get_default_committee()
        )
        self._validate_members(self.members)

    def _validate_members(
        self,
        members: Iterable[CommitteeMember],
    ) -> None:
        items = list(members)
        if not items:
            raise CommitteeValidationError(
                "committee must contain at least one member"
            )

        ids: set[str] = set()
        for member in items:
            if not isinstance(member, CommitteeMember):
                raise CommitteeValidationError(
                    "all members must be CommitteeMember instances"
                )
            if member.member_id in ids:
                raise CommitteeValidationError(
                    f"duplicate committee member: {member.member_id}"
                )
            ids.add(member.member_id)

        if not any(member.enabled for member in items):
            raise CommitteeValidationError(
                "at least one committee member must be enabled"
            )

    def _get_task(self, task_id: str) -> Any:
        if not task_id or not isinstance(task_id, str):
            raise CommitteeValidationError("task_id must be a non-empty string")

        try:
            task = self.task_manager.get_task(task_id)
        except Exception as exc:
            raise CommitteeTaskNotFoundError(
                f"unable to retrieve task {task_id}: {exc}"
            ) from exc

        if task is None:
            raise CommitteeTaskNotFoundError(
                f"task not found: {task_id}"
            )
        return task

    def _get_consensus(
        self,
        consensus_report: Any = None,
        consensus_id: Optional[str] = None,
    ) -> Any:
        if consensus_report is not None and consensus_id is not None:
            raise CommitteeConsensusError(
                "provide consensus_report or consensus_id, not both"
            )

        if consensus_report is not None:
            return consensus_report

        if not consensus_id:
            raise CommitteeConsensusError(
                "consensus_report or consensus_id is required"
            )

        try:
            report = self.consensus_engine.get_report(consensus_id)
        except Exception as exc:
            raise CommitteeConsensusError(
                f"unable to retrieve consensus {consensus_id}: {exc}"
            ) from exc

        if report is None:
            raise CommitteeConsensusError(
                f"consensus report not found: {consensus_id}"
            )
        return report

    def _validate_consensus(
        self,
        task_id: str,
        report: Any,
    ) -> None:
        report_task_id = _read_field(report, "task_id")
        report_consensus_id = _read_field(report, "consensus_id")
        status = _read_field(report, "status")
        confidence = _normalize_confidence(
            _read_field(report, "confidence")
        )

        if report_task_id != task_id:
            raise CommitteeConsensusError(
                "consensus task_id does not match requested task_id"
            )
        if not report_consensus_id:
            raise CommitteeConsensusError("consensus_id is missing")
        if status is None:
            raise CommitteeConsensusError("consensus status is missing")
        if confidence < 0.0 or confidence > 1.0:
            raise CommitteeConsensusError(
                "consensus confidence must be between 0 and 1"
            )

        # 契约校验集中在入口：未知状态在这里就拦下；
        # _calculate_decision 里保留同样的防御检查，避免绕过校验直接调用。
        normalized_status = self._consensus_status(report)
        if normalized_status not in _KNOWN_CONSENSUS_STATUSES:
            raise CommitteeConsensusError(
                f"unknown consensus status: {normalized_status!r}"
            )

    def _normalize_ballots(
        self,
        ballots: Optional[Iterable[CommitteeBallot | Mapping[str, Any]]],
        active_members: list[CommitteeMember],
    ) -> list[CommitteeBallot]:
        if ballots is None:
            return []

        member_map = {member.member_id: member for member in active_members}
        normalized: list[CommitteeBallot] = []
        seen: set[str] = set()

        for item in ballots:
            if isinstance(item, CommitteeBallot):
                ballot = item
            elif isinstance(item, Mapping):
                try:
                    ballot = CommitteeBallot(
                        member_id=str(item["member_id"]),
                        vote=CommitteeVote(item["vote"]),
                        rationale=str(item.get("rationale", "")),
                        conditions=tuple(item.get("conditions", [])),
                        risk_flags=tuple(item.get("risk_flags", [])),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise CommitteeValidationError(
                        f"invalid ballot: {exc}"
                    ) from exc
            else:
                raise CommitteeValidationError(
                    "ballots must contain CommitteeBallot or mapping values"
                )

            if ballot.member_id not in member_map:
                raise CommitteeValidationError(
                    f"unknown or inactive committee member: {ballot.member_id}"
                )
            if ballot.member_id in seen:
                raise CommitteeValidationError(
                    f"duplicate ballot from member: {ballot.member_id}"
                )

            seen.add(ballot.member_id)
            normalized.append(ballot)

        return normalized

    def _consensus_status(self, report: Any) -> str:
        status = _read_field(report, "status")
        return str(getattr(status, "value", status)).lower()

    def _consensus_confidence(self, report: Any) -> float:
        # consensus_engine 的 confidence 是 high/medium/low 文字等级，
        # 判定阶段必须先映射成 0~1 数值，否则会被当成 0 而误判为证据不足。
        return _normalize_confidence(_read_field(report, "confidence"))

    def _consensus_risks(self, report: Any) -> list[str]:
        values = _read_field(report, "risk_warnings", [])
        if values is None:
            return []
        if not isinstance(values, (list, tuple)):
            raise CommitteeConsensusError(
                "consensus risk_warnings must be a list or tuple"
            )
        return [str(value) for value in values]

    def _consensus_conclusion(self, report: Any) -> str:
        value = _read_field(report, "conclusion", "")
        return str(value or "")

    # --------------------------------------------------------
    # Decision calculation
    # --------------------------------------------------------

    def _calculate_decision(
        self,
        report: Any,
        active_members: list[CommitteeMember],
        ballots: list[CommitteeBallot],
        rationale: str,
        force: bool,
    ) -> CommitteeDecision:
        member_map = {
            member.member_id: member for member in active_members
        }
        ballot_map = {
            ballot.member_id: ballot for ballot in ballots
        }

        total_count = len(active_members)
        participation_count = len(ballots)

        participation_rate = (
            participation_count / total_count if total_count else 0.0
        )
        quorum_met = participation_rate >= self.quorum

        required_ids = {
            member.member_id
            for member in active_members
            if member.required
        }
        required_members_met = required_ids.issubset(
            set(ballot_map.keys())
        )

        total_weight = sum(
            member_map[ballot.member_id].weight
            for ballot in ballots
        )

        positive_weight = sum(
            member_map[ballot.member_id].weight
            for ballot in ballots
            if ballot.vote in (
                CommitteeVote.APPROVE,
                CommitteeVote.APPROVE_WITH_CONDITIONS,
            )
        )

        approval_score = (
            positive_weight / total_weight if total_weight > 0 else 0.0
        )

        conditions: list[str] = []
        risk_flags: list[str] = self._consensus_risks(report)

        for ballot in ballots:
            conditions.extend(ballot.conditions)
            risk_flags.extend(ballot.risk_flags)

        conditions = list(dict.fromkeys(conditions))
        risk_flags = list(dict.fromkeys(risk_flags))

        rejected_roles = {
            CommitteeRole.RISK_OFFICER,
            CommitteeRole.COMPLIANCE_OFFICER,
        }
        veto_votes = [
            ballot
            for ballot in ballots
            if ballot.vote == CommitteeVote.REJECT
            and member_map[ballot.member_id].role in rejected_roles
        ]
        veto_triggered = self.risk_veto_enabled and bool(veto_votes)

        consensus_status = self._consensus_status(report)
        # 共识层只产出这四种状态；未知值（如 failed/pending 或改名）必须报错，
        # 不能被默认当成“完全共识”放行。
        if consensus_status not in _KNOWN_CONSENSUS_STATUSES:
            raise CommitteeConsensusError(
                f"unknown consensus status: {consensus_status!r}"
            )
        confidence = self._consensus_confidence(report)

        insufficient_consensus = consensus_status in {
            "no_consensus",
            "insufficient_evidence",
        }
        partial_consensus = consensus_status == "partial_consensus"

        if not quorum_met or not required_members_met:
            status = CommitteeStatus.DEFERRED

        elif insufficient_consensus:
            status = CommitteeStatus.INSUFFICIENT_EVIDENCE

        # 一票否决必须先于置信度判定：否则风控/合规 reject 会因置信度不足
        # 被判成 INSUFFICIENT_EVIDENCE，但 metadata.veto_triggered 仍为 True。
        elif veto_triggered:
            status = CommitteeStatus.REJECTED

        elif confidence < self.minimum_confidence:
            status = CommitteeStatus.INSUFFICIENT_EVIDENCE

        elif not ballots:
            status = CommitteeStatus.DEFERRED

        elif approval_score < self.approval_threshold:
            status = CommitteeStatus.REJECTED

        elif any(
            ballot.vote == CommitteeVote.APPROVE_WITH_CONDITIONS
            for ballot in ballots
        ) or conditions or risk_flags or partial_consensus:
            status = CommitteeStatus.APPROVED_WITH_CONDITIONS

        else:
            status = CommitteeStatus.APPROVED

        if veto_triggered:
            veto_members = [
                member_map[ballot.member_id].name
                for ballot in veto_votes
            ]
            risk_flags.append(
                "Committee risk/compliance veto: "
                + ", ".join(veto_members)
            )

        # 否决票是既成事实，但只有在决议本可成立时才具备决定性；
        # quorum 不足或共识层判定证据不足时，会议本身不成立，
        # 这里显式区分“程序性不成立”和“实质否决”，便于审计复核。
        veto_decisive = veto_triggered and status == CommitteeStatus.REJECTED

        recommendation = self._build_recommendation(
            status=status,
            consensus_report=report,
            conditions=conditions,
            risk_flags=risk_flags,
        )

        decision_rationale = rationale.strip()
        if not decision_rationale:
            decision_rationale = (
                f"Committee decision based on consensus "
                f"{_read_field(report, 'consensus_id')}."
            )

        if force:
            decision_rationale += (
                " Decision was recorded with force=True; "
                "this does not bypass quorum, confidence, or veto rules."
            )

        if veto_triggered and not veto_decisive:
            decision_rationale += (
                " A risk/compliance veto was cast but is not decisive: "
                "the motion never reached a decidable state "
                f"(status={status.value})."
            )

        decision = CommitteeDecision(
            decision_id=f"IC-{uuid.uuid4().hex[:12]}",
            task_id=str(_read_field(report, "task_id")),
            consensus_id=str(_read_field(report, "consensus_id")),
            status=status,
            members=active_members,
            ballots=ballots,
            approval_score=round(approval_score, 6),
            participation_rate=round(participation_rate, 6),
            quorum_met=quorum_met,
            required_members_met=required_members_met,
            conditions=conditions,
            risk_flags=risk_flags,
            rationale=decision_rationale,
            recommendation=recommendation,
            metadata={
                "consensus_status": consensus_status,
                "consensus_confidence": confidence,
                "consensus_agreement_score": _as_float(
                    _read_field(report, "agreement_score")
                ),
                "consensus_evidence_score": _as_float(
                    _read_field(report, "evidence_score")
                ),
                "approval_threshold": self.approval_threshold,
                "quorum_threshold": self.quorum,
                "minimum_confidence": self.minimum_confidence,
                "risk_veto_enabled": self.risk_veto_enabled,
                "veto_triggered": veto_triggered,
                "veto_decisive": veto_decisive,
                "force": bool(force),
            },
        )
        return decision

    @staticmethod
    def _build_recommendation(
        status: CommitteeStatus,
        consensus_report: Any,
        conditions: list[str],
        risk_flags: list[str],
    ) -> str:
        consensus_id = _read_field(
            consensus_report, "consensus_id", "unknown"
        )

        if status == CommitteeStatus.APPROVED:
            return (
                f"Committee approved the research conclusion "
                f"based on consensus {consensus_id}. "
                "This is a research governance decision, not an order."
            )

        if status == CommitteeStatus.APPROVED_WITH_CONDITIONS:
            details = "; ".join(conditions + risk_flags)
            suffix = f" Conditions and risks: {details}" if details else ""
            return (
                f"Committee approved the research conclusion with "
                f"conditions based on consensus {consensus_id}."
                f"{suffix} This is not an order."
            )

        if status == CommitteeStatus.REJECTED:
            return (
                f"Committee rejected the proposal based on consensus "
                f"{consensus_id}. Further research or risk review is "
                "required. No trading action is authorized."
            )

        if status == CommitteeStatus.INSUFFICIENT_EVIDENCE:
            return (
                f"Evidence is insufficient for committee approval "
                f"based on consensus {consensus_id}. "
                "Collect additional evidence and re-evaluate."
            )

        return (
            f"Committee decision deferred for consensus {consensus_id}. "
            "Quorum or required-member participation was not satisfied."
        )

    # --------------------------------------------------------
    # Public decision API
    # --------------------------------------------------------

    def convene(
        self,
        task_id: str,
        consensus_report: Any = None,
        consensus_id: Optional[str] = None,
        ballots: Optional[
            Iterable[CommitteeBallot | Mapping[str, Any]]
        ] = None,
        members: Optional[Iterable[CommitteeMember]] = None,
        rationale: str = "",
        force: bool = False,
    ) -> CommitteeDecision:
        """
        Convene the committee and record its decision.

        ballots may contain CommitteeBallot instances or mappings:
        {
            "member_id": "cio",
            "vote": "approve",
            "rationale": "...",
            "conditions": [],
            "risk_flags": []
        }
        """

        self._get_task(task_id)

        report = self._get_consensus(
            consensus_report=consensus_report,
            consensus_id=consensus_id,
        )
        self._validate_consensus(task_id, report)

        active_members = list(
            members if members is not None else self.members
        )
        self._validate_members(active_members)
        active_members = [
            member for member in active_members if member.enabled
        ]

        normalized_ballots = self._normalize_ballots(
            ballots=ballots,
            active_members=active_members,
        )

        decision = self._calculate_decision(
            report=report,
            active_members=active_members,
            ballots=normalized_ballots,
            rationale=rationale,
            force=force,
        )

        self.save_decision(decision)
        return decision

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def _decision_path(self, decision_id: str) -> Path:
        safe_id = _safe_filename(decision_id)
        return self.storage_dir / f"committee_{safe_id}.json"

    def save_decision(
        self,
        decision: CommitteeDecision,
    ) -> Path:
        if not isinstance(decision, CommitteeDecision):
            raise CommitteeValidationError(
                "decision must be CommitteeDecision"
            )

        path = self._decision_path(decision.decision_id)

        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            temporary_path = path.with_suffix(".json.tmp")
            temporary_path.write_text(
                json.dumps(
                    decision.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary_path.replace(path)
        except OSError as exc:
            raise CommitteePersistenceError(
                f"failed to save committee decision: {exc}"
            ) from exc

        return path

    def get_decision(self, decision_id: str) -> CommitteeDecision:
        if not decision_id:
            raise CommitteeValidationError("decision_id is required")

        path = self._decision_path(decision_id)
        if not path.exists():
            raise CommitteeNotFoundError(
                f"committee decision not found: {decision_id}"
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return CommitteeDecision.from_dict(data)
        except CommitteeNotFoundError:
            raise
        except (OSError, json.JSONDecodeError, CommitteeValidationError) as exc:
            raise CommitteePersistenceError(
                f"failed to load committee decision: {exc}"
            ) from exc

    def list_decisions(
        self,
        task_id: Optional[str] = None,
        status: Optional[CommitteeStatus | str] = None,
    ) -> list[CommitteeDecision]:
        if status is not None:
            try:
                normalized_status = CommitteeStatus(
                    getattr(status, "value", status)
                )
            except ValueError as exc:
                raise CommitteeValidationError(
                    f"invalid committee status: {status}"
                ) from exc
        else:
            normalized_status = None

        decisions: list[CommitteeDecision] = []

        try:
            paths = sorted(
                self.storage_dir.glob("committee_*.json")
            )
            for path in paths:
                data = json.loads(path.read_text(encoding="utf-8"))
                decision = CommitteeDecision.from_dict(data)

                if task_id is not None and decision.task_id != task_id:
                    continue
                if (
                    normalized_status is not None
                    and decision.status != normalized_status
                ):
                    continue

                decisions.append(decision)

        except (OSError, json.JSONDecodeError, CommitteeValidationError) as exc:
            raise CommitteePersistenceError(
                f"failed to list committee decisions: {exc}"
            ) from exc

        return decisions

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------

    def export_decision(self, decision_id: str) -> dict[str, Any]:
        decision = self.get_decision(decision_id)
        return decision.to_dict()

    def export_markdown(self, decision_id: str) -> str:
        decision = self.get_decision(decision_id)

        lines = [
            "# Investment Committee Decision",
            "",
            f"- Decision ID: `{decision.decision_id}`",
            f"- Task ID: `{decision.task_id}`",
            f"- Consensus ID: `{decision.consensus_id}`",
            f"- Status: **{decision.status.value}**",
            f"- Approval score: {decision.approval_score:.2%}",
            f"- Participation rate: {decision.participation_rate:.2%}",
            f"- Quorum met: {decision.quorum_met}",
            f"- Required members met: {decision.required_members_met}",
            f"- Created at: {decision.created_at}",
            "",
            "## Recommendation",
            "",
            decision.recommendation,
            "",
            "## Rationale",
            "",
            decision.rationale or "No additional rationale provided.",
            "",
            "## Committee Members",
            "",
            "| Member | Role | Weight | Required |",
            "|---|---|---:|---|",
        ]

        for member in decision.members:
            lines.append(
                f"| {member.name} | {member.role.value} | "
                f"{member.weight:.2f} | {member.required} |"
            )

        lines.extend([
            "",
            "## Ballots",
            "",
            "| Member ID | Vote | Rationale |",
            "|---|---|---|",
        ])

        for ballot in decision.ballots:
            safe_rationale = ballot.rationale.replace("|", "\\|").replace(
                "\n", " "
            )
            lines.append(
                f"| {ballot.member_id} | {ballot.vote.value} | "
                f"{safe_rationale} |"
            )

        lines.extend([
            "",
            "## Conditions",
            "",
        ])
        if decision.conditions:
            lines.extend(f"- {item}" for item in decision.conditions)
        else:
            lines.append("- None")

        lines.extend([
            "",
            "## Risk Flags",
            "",
        ])
        if decision.risk_flags:
            lines.extend(f"- {item}" for item in decision.risk_flags)
        else:
            lines.append("- None")

        lines.extend([
            "",
            "## Governance Notice",
            "",
            "This document records a research and governance decision only. "
            "It does not constitute an investment order, brokerage instruction, "
            "or authorization to execute a live trade.",
            "",
        ])

        return "\n".join(lines)

    def get_committee_summary(self) -> dict[str, Any]:
        decisions = self.list_decisions()

        counts = {
            status.value: 0
            for status in CommitteeStatus
        }
        for decision in decisions:
            counts[decision.status.value] += 1

        return {
            "total_decisions": len(decisions),
            "status_counts": counts,
            "committee_members": len(self.members),
            "enabled_members": sum(
                1 for member in self.members if member.enabled
            ),
            "quorum": self.quorum,
            "approval_threshold": self.approval_threshold,
            "minimum_confidence": self.minimum_confidence,
        }
