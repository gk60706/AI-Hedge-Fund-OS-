# tests/ai_team/test_investment_committee.py

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ai_team.investment_committee import (
    InvestmentCommittee,
    InvestmentCommitteeError,
    CommitteeTaskNotFoundError,
    CommitteeConsensusError,
    CommitteeValidationError,
    CommitteeNotFoundError,
    CommitteePersistenceError,
    CommitteeStatus,
    CommitteeVote,
    CommitteeRole,
    CommitteeMember,
    CommitteeBallot,
    CommitteeDecision,
    get_default_committee,
)


# ============================================================
# Fakes
# ============================================================

class FakeTaskManager:
    def __init__(self, tasks=None):
        self.tasks = tasks or {
            "TASK-001": SimpleNamespace(
                task_id="TASK-001",
                title="AI infrastructure research",
                status="completed",
            ),
            "TASK-002": SimpleNamespace(
                task_id="TASK-002",
                title="Semiconductor industry research",
                status="completed",
            ),
        }

    def get_task(self, task_id):
        return self.tasks.get(task_id)


class FakeConsensusEngine:
    def __init__(self, reports=None, storage_dir=None):
        self.reports = reports or {}
        self.storage_dir = Path(
            storage_dir or tempfile.gettempdir()
        )

    def get_report(self, consensus_id):
        return self.reports.get(consensus_id)


def make_consensus(
    task_id="TASK-001",
    consensus_id="CON-001",
    status="consensus",
    confidence=0.85,
    agreement_score=0.80,
    evidence_score=0.75,
    risk_warnings=None,
    conclusion="Research evidence supports further evaluation.",
):
    return SimpleNamespace(
        task_id=task_id,
        consensus_id=consensus_id,
        validation_id="VAL-001",
        debate_id="DEB-001",
        status=status,
        confidence=confidence,
        agreement_score=agreement_score,
        position_agreement=agreement_score,
        evidence_score=evidence_score,
        participants=["chatgpt", "grok", "hark"],
        votes=[],
        issues=[],
        consensus_points=["Demand growth", "Capacity expansion"],
        unresolved_issues=[],
        conclusion=conclusion,
        risk_warnings=risk_warnings or [],
        metadata={},
        created_at="2026-11-14T00:00:00+00:00",
    )


def make_ballot(
    member_id,
    vote="approve",
    rationale="Reviewed the research.",
    conditions=None,
    risk_flags=None,
):
    return CommitteeBallot(
        member_id=member_id,
        vote=CommitteeVote(vote),
        rationale=rationale,
        conditions=tuple(conditions or []),
        risk_flags=tuple(risk_flags or []),
    )


def make_full_approval_ballots():
    return [
        make_ballot("cio", "approve"),
        make_ballot("risk", "approve"),
        make_ballot("compliance", "approve"),
        make_ballot("quant", "approve"),
        make_ballot("fundamental", "approve"),
    ]


# ============================================================
# Test setup
# ============================================================

class InvestmentCommitteeTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.temp_dir.name) / "committee"

        self.task_manager = FakeTaskManager()

        self.consensus = make_consensus()
        self.consensus_engine = FakeConsensusEngine(
            reports={"CON-001": self.consensus},
            storage_dir=Path(self.temp_dir.name) / "consensus",
        )

        self.committee = InvestmentCommittee(
            task_manager=self.task_manager,
            consensus_engine=self.consensus_engine,
            storage_dir=self.storage_dir,
        )

    def tearDown(self):
        self.temp_dir.cleanup()


# ============================================================
# Initialization tests
# ============================================================

class TestCommitteeInitialization(InvestmentCommitteeTestCase):

    def test_initialization(self):
        self.assertEqual(self.committee.quorum, 0.60)
        self.assertEqual(self.committee.approval_threshold, 0.67)
        self.assertEqual(self.committee.minimum_confidence, 0.50)
        self.assertTrue(self.storage_dir.exists())

    def test_default_committee_contains_required_roles(self):
        members = get_default_committee()

        roles = {member.role for member in members}

        self.assertIn(CommitteeRole.CHIEF_INVESTMENT_OFFICER, roles)
        self.assertIn(CommitteeRole.RISK_OFFICER, roles)
        self.assertIn(CommitteeRole.COMPLIANCE_OFFICER, roles)

    def test_default_committee_has_required_members(self):
        members = get_default_committee()

        required = [
            member for member in members if member.required
        ]

        self.assertGreaterEqual(len(required), 2)

    def test_custom_committee(self):
        members = [
            CommitteeMember(
                member_id="chair",
                name="Committee Chair",
                role=CommitteeRole.CHIEF_INVESTMENT_OFFICER,
                required=True,
            ),
            CommitteeMember(
                member_id="analyst",
                name="Research Analyst",
                role=CommitteeRole.QUANT_ANALYST,
            ),
        ]

        committee = InvestmentCommittee(
            self.task_manager,
            self.consensus_engine,
            storage_dir=self.storage_dir / "custom",
            members=members,
        )

        self.assertEqual(len(committee.members), 2)

    def test_missing_task_manager_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            InvestmentCommittee(
                None,
                self.consensus_engine,
            )

    def test_missing_consensus_engine_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            InvestmentCommittee(
                self.task_manager,
                None,
            )

    def test_invalid_quorum_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            InvestmentCommittee(
                self.task_manager,
                self.consensus_engine,
                quorum=1.5,
            )

    def test_negative_approval_threshold_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            InvestmentCommittee(
                self.task_manager,
                self.consensus_engine,
                approval_threshold=-0.1,
            )

    def test_invalid_confidence_threshold_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            InvestmentCommittee(
                self.task_manager,
                self.consensus_engine,
                minimum_confidence=2.0,
            )

    def test_empty_committee_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            InvestmentCommittee(
                self.task_manager,
                self.consensus_engine,
                members=[],
            )

    def test_duplicate_member_id_rejected(self):
        members = [
            CommitteeMember(
                "same",
                "Member A",
                CommitteeRole.QUANT_ANALYST,
            ),
            CommitteeMember(
                "same",
                "Member B",
                CommitteeRole.INDUSTRY_ANALYST,
            ),
        ]

        with self.assertRaises(CommitteeValidationError):
            InvestmentCommittee(
                self.task_manager,
                self.consensus_engine,
                members=members,
            )

    def test_member_weight_must_be_positive(self):
        with self.assertRaises(CommitteeValidationError):
            CommitteeMember(
                member_id="bad",
                name="Bad Member",
                role=CommitteeRole.QUANT_ANALYST,
                weight=0,
            )

    def test_member_weight_rejects_boolean(self):
        with self.assertRaises(CommitteeValidationError):
            CommitteeMember(
                member_id="bad",
                name="Bad Member",
                role=CommitteeRole.QUANT_ANALYST,
                weight=True,
            )

    def test_member_role_must_be_enum(self):
        with self.assertRaises(CommitteeValidationError):
            CommitteeMember(
                member_id="bad",
                name="Bad Member",
                role="quant_analyst",
            )


# ============================================================
# Task and consensus validation tests
# ============================================================

class TestCommitteeInputValidation(InvestmentCommitteeTestCase):

    def test_unknown_task_rejected(self):
        with self.assertRaises(CommitteeTaskNotFoundError):
            self.committee.convene(
                task_id="UNKNOWN",
                consensus_report=self.consensus,
                ballots=make_full_approval_ballots(),
            )

    def test_empty_task_id_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            self.committee.convene(
                task_id="",
                consensus_report=self.consensus,
            )

    def test_missing_consensus_rejected(self):
        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(task_id="TASK-001")

    def test_unknown_consensus_id_rejected(self):
        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                task_id="TASK-001",
                consensus_id="UNKNOWN",
            )

    def test_consensus_id_lookup(self):
        decision = self.committee.convene(
            task_id="TASK-001",
            consensus_id="CON-001",
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(decision.consensus_id, "CON-001")

    def test_report_and_id_together_rejected(self):
        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                task_id="TASK-001",
                consensus_report=self.consensus,
                consensus_id="CON-001",
            )

    def test_mismatched_task_id_rejected(self):
        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                task_id="TASK-002",
                consensus_report=self.consensus,
            )

    def test_missing_consensus_id_rejected(self):
        invalid = make_consensus()
        invalid.consensus_id = ""

        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                task_id="TASK-001",
                consensus_report=invalid,
            )

    def test_missing_consensus_status_rejected(self):
        invalid = make_consensus()
        invalid.status = None

        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                task_id="TASK-001",
                consensus_report=invalid,
            )

    def test_invalid_confidence_rejected(self):
        invalid = make_consensus(confidence=1.5)

        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                task_id="TASK-001",
                consensus_report=invalid,
            )

    def test_invalid_risk_warnings_type_rejected(self):
        invalid = make_consensus()
        invalid.risk_warnings = "not-a-list"

        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                task_id="TASK-001",
                consensus_report=invalid,
            )


# ============================================================
# Ballot validation tests
# ============================================================

class TestCommitteeBallotValidation(InvestmentCommitteeTestCase):

    def test_unknown_member_ballot_rejected(self):
        ballots = [
            make_ballot("unknown", "approve"),
        ]

        with self.assertRaises(CommitteeValidationError):
            self.committee.convene(
                "TASK-001",
                consensus_report=self.consensus,
                ballots=ballots,
            )

    def test_duplicate_ballot_rejected(self):
        ballots = [
            make_ballot("cio"),
            make_ballot("cio"),
        ]

        with self.assertRaises(CommitteeValidationError):
            self.committee.convene(
                "TASK-001",
                consensus_report=self.consensus,
                ballots=ballots,
            )

    def test_invalid_vote_rejected(self):
        ballots = [{
            "member_id": "cio",
            "vote": "maybe",
        }]

        with self.assertRaises(CommitteeValidationError):
            self.committee.convene(
                "TASK-001",
                consensus_report=self.consensus,
                ballots=ballots,
            )

    def test_mapping_ballot_supported(self):
        ballots = [
            {
                "member_id": "cio",
                "vote": "approve",
                "rationale": "Reviewed.",
                "conditions": [],
                "risk_flags": [],
            },
            {
                "member_id": "risk",
                "vote": "approve",
            },
            {
                "member_id": "compliance",
                "vote": "approve",
            },
        ]

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=ballots,
        )

        self.assertEqual(len(decision.ballots), 3)

    def test_invalid_ballot_object_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            self.committee.convene(
                "TASK-001",
                consensus_report=self.consensus,
                ballots=[object()],
            )


# ============================================================
# Voting and decision tests
# ============================================================

class TestCommitteeDecisionRules(InvestmentCommitteeTestCase):

    def test_full_approval(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(decision.status, CommitteeStatus.APPROVED)
        self.assertTrue(decision.quorum_met)
        self.assertTrue(decision.required_members_met)
        self.assertEqual(decision.approval_score, 1.0)

    def test_approval_score_uses_member_weights(self):
        members = [
            CommitteeMember(
                "cio",
                "CIO",
                CommitteeRole.CHIEF_INVESTMENT_OFFICER,
                weight=3.0,
                required=True,
            ),
            CommitteeMember(
                "risk",
                "Risk",
                CommitteeRole.RISK_OFFICER,
                weight=1.0,
                required=True,
            ),
        ]

        committee = InvestmentCommittee(
            self.task_manager,
            self.consensus_engine,
            storage_dir=self.storage_dir / "weighted",
            members=members,
            quorum=1.0,
            approval_threshold=0.60,
        )

        decision = committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio", "approve"),
                make_ballot("risk", "reject"),
            ],
        )

        self.assertAlmostEqual(decision.approval_score, 0.75)
        # 风险官（RISK_OFFICER）投反对票时默认触发一票否决，
        # 即使加权通过率 0.75 已高于 approval_threshold=0.60，
        # 最终决议仍为 REJECTED（与 test_risk_officer_veto 保持一致）。
        self.assertEqual(decision.status, CommitteeStatus.REJECTED)
        self.assertTrue(decision.metadata["veto_triggered"])

    def test_insufficient_quorum_defers_decision(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio"),
            ],
        )

        self.assertEqual(decision.status, CommitteeStatus.DEFERRED)
        self.assertFalse(decision.quorum_met)

    def test_missing_required_member_defers_decision(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio"),
                make_ballot("quant"),
                make_ballot("fundamental"),
                make_ballot("industry"),
            ],
        )

        self.assertFalse(decision.required_members_met)
        self.assertEqual(decision.status, CommitteeStatus.DEFERRED)

    def test_rejection_below_threshold(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio", "reject"),
                make_ballot("risk", "approve"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "reject"),
                make_ballot("fundamental", "reject"),
            ],
        )

        self.assertEqual(decision.status, CommitteeStatus.REJECTED)
        self.assertLess(
            decision.approval_score,
            self.committee.approval_threshold,
        )

    def test_conditional_approval(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio", "approve"),
                make_ballot("risk", "approve_with_conditions"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "approve"),
                make_ballot("fundamental", "approve"),
            ],
        )

        self.assertEqual(
            decision.status,
            CommitteeStatus.APPROVED_WITH_CONDITIONS,
        )

    def test_conditions_are_collected(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot(
                    "cio",
                    "approve_with_conditions",
                    conditions=["Recheck valuation"],
                ),
                make_ballot("risk", "approve"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "approve"),
                make_ballot("fundamental", "approve"),
            ],
        )

        self.assertIn("Recheck valuation", decision.conditions)

    def test_ballot_risk_flags_are_collected(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot(
                    "cio",
                    "approve",
                    risk_flags=["Liquidity risk"],
                ),
                make_ballot("risk", "approve"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "approve"),
                make_ballot("fundamental", "approve"),
            ],
        )

        self.assertIn("Liquidity risk", decision.risk_flags)

    def test_consensus_risk_warnings_are_preserved(self):
        report = make_consensus(
            risk_warnings=["Data coverage is incomplete"]
        )

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=make_full_approval_ballots(),
        )

        self.assertIn(
            "Data coverage is incomplete",
            decision.risk_flags,
        )

    def test_risk_officer_veto(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio", "approve"),
                make_ballot("risk", "reject"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "approve"),
                make_ballot("fundamental", "approve"),
            ],
        )

        self.assertEqual(decision.status, CommitteeStatus.REJECTED)
        self.assertTrue(decision.metadata["veto_triggered"])

    def test_compliance_officer_veto(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio", "approve"),
                make_ballot("risk", "approve"),
                make_ballot("compliance", "reject"),
                make_ballot("quant", "approve"),
                make_ballot("fundamental", "approve"),
            ],
        )

        self.assertEqual(decision.status, CommitteeStatus.REJECTED)
        self.assertTrue(decision.metadata["veto_triggered"])

    def test_veto_can_be_disabled(self):
        committee = InvestmentCommittee(
            self.task_manager,
            self.consensus_engine,
            storage_dir=self.storage_dir / "no-veto",
            risk_veto_enabled=False,
        )

        decision = committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio", "approve"),
                make_ballot("risk", "reject"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "approve"),
                make_ballot("fundamental", "approve"),
            ],
        )

        self.assertFalse(decision.metadata["veto_triggered"])
        self.assertEqual(
            decision.status,
            CommitteeStatus.APPROVED,
        )

    def test_no_consensus_produces_insufficient_evidence(self):
        report = make_consensus(status="no_consensus")

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(
            decision.status,
            CommitteeStatus.INSUFFICIENT_EVIDENCE,
        )

    def test_insufficient_evidence_status_preserved(self):
        report = make_consensus(status="insufficient_evidence")

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(
            decision.status,
            CommitteeStatus.INSUFFICIENT_EVIDENCE,
        )

    def test_low_confidence_produces_insufficient_evidence(self):
        report = make_consensus(confidence=0.30)

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(
            decision.status,
            CommitteeStatus.INSUFFICIENT_EVIDENCE,
        )

    def test_partial_consensus_requires_conditions(self):
        report = make_consensus(status="partial_consensus")

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(
            decision.status,
            CommitteeStatus.APPROVED_WITH_CONDITIONS,
        )

    def test_force_does_not_bypass_quorum(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[make_ballot("cio")],
            force=True,
        )

        self.assertEqual(decision.status, CommitteeStatus.DEFERRED)
        self.assertFalse(decision.quorum_met)
        self.assertIn("force=True", decision.rationale)

    def test_abstain_counts_as_participation_not_approval(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("cio", "approve"),
                make_ballot("risk", "abstain"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "abstain"),
                make_ballot("fundamental", "abstain"),
            ],
        )

        self.assertTrue(decision.quorum_met)
        self.assertLess(decision.approval_score, 1.0)

    def test_text_confidence_is_not_treated_as_zero(self):
        """共识层给的是 high/medium/low 文字等级，不能解析成 0 而误判证据不足。"""

        report = make_consensus(confidence="high")

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(decision.status, CommitteeStatus.APPROVED)
        self.assertAlmostEqual(
            decision.metadata["consensus_confidence"],
            0.8,
        )

    def test_unknown_consensus_status_is_rejected(self):
        """未知 status 不能被当成完全共识放行。"""

        report = make_consensus(status="failed")

        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                "TASK-001",
                consensus_report=report,
                ballots=make_full_approval_ballots(),
            )

    def test_veto_wins_over_low_confidence(self):
        """否决票必须先于置信度判定，避免 veto_triggered=True 却判证据不足。"""

        report = make_consensus(confidence=0.30)

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=[
                make_ballot("cio", "approve"),
                make_ballot("risk", "reject"),
                make_ballot("compliance", "approve"),
                make_ballot("quant", "approve"),
                make_ballot("fundamental", "approve"),
            ],
        )

        self.assertEqual(decision.status, CommitteeStatus.REJECTED)
        self.assertTrue(decision.metadata["veto_triggered"])

    def test_status_whitelist_matches_consensus_engine(self):
        """状态白名单必须与共识层枚举同步，共识层新增状态时这里要失败提醒。"""

        from ai_team.consensus_engine import ConsensusStatus
        from ai_team.investment_committee import _KNOWN_CONSENSUS_STATUSES

        self.assertEqual(
            _KNOWN_CONSENSUS_STATUSES,
            {status.value for status in ConsensusStatus},
        )

    def test_low_text_confidence_produces_insufficient_evidence(self):
        report = make_consensus(confidence="low")

        decision = self.committee.convene(
            "TASK-001",
            consensus_report=report,
            ballots=make_full_approval_ballots(),
        )

        self.assertEqual(
            decision.status,
            CommitteeStatus.INSUFFICIENT_EVIDENCE,
        )

    def test_nan_confidence_is_treated_as_invalid(self):
        """NaN 无法参与阈值比较，必须按契约错误显式拒绝，而不是静默放行。"""

        report = make_consensus(confidence=float("nan"))

        with self.assertRaises(CommitteeConsensusError):
            self.committee.convene(
                "TASK-001",
                consensus_report=report,
                ballots=make_full_approval_ballots(),
            )


# ============================================================
# Persistence and export tests
# ============================================================

class TestCommitteePersistence(InvestmentCommitteeTestCase):

    def _create_decision(self):
        return self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=make_full_approval_ballots(),
            rationale="Committee reviewed the evidence.",
        )

    def test_decision_is_persisted(self):
        decision = self._create_decision()

        path = (
            self.storage_dir
            / f"committee_{decision.decision_id}.json"
        )

        self.assertTrue(path.exists())

    def test_persisted_json_is_valid(self):
        decision = self._create_decision()

        path = (
            self.storage_dir
            / f"committee_{decision.decision_id}.json"
        )

        data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["decision_id"], decision.decision_id)
        self.assertEqual(data["task_id"], "TASK-001")
        self.assertEqual(data["status"], "approved")

    def test_get_decision(self):
        original = self._create_decision()

        loaded = self.committee.get_decision(
            original.decision_id
        )

        self.assertEqual(
            loaded.decision_id,
            original.decision_id,
        )
        self.assertEqual(loaded.status, original.status)
        self.assertEqual(
            loaded.approval_score,
            original.approval_score,
        )

    def test_loaded_decision_preserves_members(self):
        original = self._create_decision()

        loaded = self.committee.get_decision(
            original.decision_id
        )

        self.assertEqual(len(loaded.members), len(original.members))
        self.assertEqual(
            loaded.members[0].member_id,
            original.members[0].member_id,
        )

    def test_loaded_decision_preserves_ballots(self):
        original = self._create_decision()

        loaded = self.committee.get_decision(
            original.decision_id
        )

        self.assertEqual(len(loaded.ballots), len(original.ballots))
        self.assertEqual(
            loaded.ballots[0].vote,
            original.ballots[0].vote,
        )

    def test_unknown_decision_rejected(self):
        with self.assertRaises(CommitteeNotFoundError):
            self.committee.get_decision("UNKNOWN")

    def test_list_decisions(self):
        self._create_decision()
        self._create_decision()

        decisions = self.committee.list_decisions()

        self.assertEqual(len(decisions), 2)

    def test_list_decisions_by_task(self):
        self._create_decision()

        decisions = self.committee.list_decisions(
            task_id="TASK-001"
        )
        other = self.committee.list_decisions(
            task_id="TASK-002"
        )

        self.assertEqual(len(decisions), 1)
        self.assertEqual(len(other), 0)

    def test_list_decisions_by_status(self):
        self._create_decision()

        approved = self.committee.list_decisions(
            status=CommitteeStatus.APPROVED
        )
        rejected = self.committee.list_decisions(
            status=CommitteeStatus.REJECTED
        )

        self.assertEqual(len(approved), 1)
        self.assertEqual(len(rejected), 0)

    def test_list_decisions_accepts_status_string(self):
        self._create_decision()

        decisions = self.committee.list_decisions(
            status="approved"
        )

        self.assertEqual(len(decisions), 1)

    def test_invalid_status_filter_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            self.committee.list_decisions(status="unknown")

    def test_export_decision(self):
        decision = self._create_decision()

        exported = self.committee.export_decision(
            decision.decision_id
        )

        self.assertIsInstance(exported, dict)
        self.assertEqual(
            exported["decision_id"],
            decision.decision_id,
        )

    def test_export_markdown(self):
        decision = self._create_decision()

        markdown = self.committee.export_markdown(
            decision.decision_id
        )

        self.assertIn("# Investment Committee Decision", markdown)
        self.assertIn("## Recommendation", markdown)
        self.assertIn("## Committee Members", markdown)
        self.assertIn("## Ballots", markdown)
        self.assertIn("## Governance Notice", markdown)

    def test_markdown_contains_no_live_trade_authorization(self):
        decision = self._create_decision()

        markdown = self.committee.export_markdown(
            decision.decision_id
        )

        self.assertIn("does not constitute an investment order", markdown)
        self.assertIn("authorization to execute a live trade", markdown)

    def test_summary_counts_decisions(self):
        self._create_decision()

        summary = self.committee.get_committee_summary()

        self.assertEqual(summary["total_decisions"], 1)
        self.assertEqual(
            summary["status_counts"]["approved"],
            1,
        )

    def test_summary_contains_committee_configuration(self):
        summary = self.committee.get_committee_summary()

        self.assertEqual(
            summary["committee_members"],
            len(self.committee.members),
        )
        self.assertEqual(summary["quorum"], 0.60)
        self.assertEqual(summary["approval_threshold"], 0.67)


# ============================================================
# Dataclass and serialization tests
# ============================================================

class TestCommitteeDataModels(InvestmentCommitteeTestCase):

    def test_member_is_frozen(self):
        member = CommitteeMember(
            "test",
            "Test Member",
            CommitteeRole.QUANT_ANALYST,
        )

        with self.assertRaises(Exception):
            member.name = "Changed"

    def test_ballot_is_frozen(self):
        ballot = make_ballot("cio")

        with self.assertRaises(Exception):
            ballot.rationale = "Changed"

    def test_decision_to_dict(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=make_full_approval_ballots(),
        )

        data = decision.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data["status"], "approved")
        self.assertIsInstance(data["members"], list)
        self.assertIsInstance(data["ballots"], list)

    def test_decision_from_dict(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=make_full_approval_ballots(),
        )

        restored = CommitteeDecision.from_dict(
            decision.to_dict()
        )

        self.assertEqual(
            restored.decision_id,
            decision.decision_id,
        )
        self.assertEqual(restored.status, decision.status)
        self.assertEqual(
            restored.approval_score,
            decision.approval_score,
        )

    def test_invalid_decision_data_rejected(self):
        with self.assertRaises(CommitteeValidationError):
            CommitteeDecision.from_dict({
                "decision_id": "bad",
            })

    def test_enum_values(self):
        self.assertEqual(
            CommitteeStatus.APPROVED.value,
            "approved",
        )
        self.assertEqual(
            CommitteeVote.APPROVE.value,
            "approve",
        )
        self.assertEqual(
            CommitteeRole.RISK_OFFICER.value,
            "risk_officer",
        )


# ============================================================
# Governance boundary tests
# ============================================================

class TestCommitteeGovernanceBoundaries(InvestmentCommitteeTestCase):

    def test_committee_does_not_expose_order_method(self):
        forbidden_methods = {
            "place_order",
            "submit_order",
            "execute_trade",
            "connect_broker",
            "send_order",
            "buy",
            "sell",
        }

        exposed = set(dir(self.committee))
        self.assertTrue(forbidden_methods.isdisjoint(exposed))

    def test_decision_is_research_governance_only(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=make_full_approval_ballots(),
        )

        self.assertIn("not an order", decision.recommendation.lower())

    def test_force_does_not_create_approval_without_ballots(self):
        decision = self.committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[],
            force=True,
        )

        self.assertEqual(decision.status, CommitteeStatus.DEFERRED)

    def test_disabled_members_are_not_part_of_active_quorum(self):
        members = [
            CommitteeMember(
                "chair",
                "Chair",
                CommitteeRole.CHIEF_INVESTMENT_OFFICER,
                required=True,
            ),
            CommitteeMember(
                "risk",
                "Risk",
                CommitteeRole.RISK_OFFICER,
                required=True,
                enabled=False,
            ),
        ]

        committee = InvestmentCommittee(
            self.task_manager,
            self.consensus_engine,
            storage_dir=self.storage_dir / "disabled",
            members=members,
            quorum=1.0,
        )

        decision = committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[make_ballot("chair")],
        )

        self.assertTrue(decision.quorum_met)
        self.assertTrue(decision.required_members_met)
        self.assertEqual(decision.status, CommitteeStatus.APPROVED)

    def test_required_member_must_vote(self):
        members = [
            CommitteeMember(
                "chair",
                "Chair",
                CommitteeRole.CHIEF_INVESTMENT_OFFICER,
                required=True,
            ),
            CommitteeMember(
                "risk",
                "Risk",
                CommitteeRole.RISK_OFFICER,
                required=True,
            ),
            CommitteeMember(
                "analyst",
                "Analyst",
                CommitteeRole.QUANT_ANALYST,
            ),
        ]

        committee = InvestmentCommittee(
            self.task_manager,
            self.consensus_engine,
            storage_dir=self.storage_dir / "required",
            members=members,
            quorum=0.5,
        )

        decision = committee.convene(
            "TASK-001",
            consensus_report=self.consensus,
            ballots=[
                make_ballot("chair"),
                make_ballot("analyst"),
            ],
        )

        self.assertTrue(decision.quorum_met)
        self.assertFalse(decision.required_members_met)
        self.assertEqual(decision.status, CommitteeStatus.DEFERRED)


if __name__ == "__main__":
    unittest.main()
