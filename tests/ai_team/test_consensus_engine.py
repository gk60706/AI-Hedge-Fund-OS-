import json

from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_team.consensus_engine import (
    ConsensusEngine,
    ConsensusEngineError,
    ConsensusTaskNotFoundError,
    ConsensusValidationError,
    ConsensusDebateError,
    ConsensusNotFoundError,
    ConsensusPersistenceError,
    ConsensusStatus,
    AgentPosition,
    EvidenceStrength,
    ConfidenceLevel,
    AgentConsensusVote,
    ConsensusIssue,
    ConsensusReport,
)


# ============================================================
# Fake dependencies
# ============================================================

class FakeTaskManager:
    def __init__(self):
        self.tasks = {
            "task_001": SimpleNamespace(
                task_id="task_001",
                title="AI infrastructure stock research",
                status="in_progress",
            ),
            "task_002": SimpleNamespace(
                task_id="task_002",
                title="Semiconductor industry research",
                status="in_progress",
            ),
        }

    def get_task(self, task_id):
        return self.tasks.get(task_id)


class FakeCrossValidator:
    def __init__(self, payload=None):
        self.payload = payload or {
            "task_id": "task_001",
            "validation_id": "validation_001",
            "conflicts": [],
            "consensus": [
                {
                    "description": (
                        "Operating cash flow should be monitored."
                    )
                }
            ],
            "agent_analyses": [
                {"agent_id": "chatgpt"},
                {"agent_id": "grok"},
                {"agent_id": "hark"},
            ],
            "agreement_score": 0.85,
            "requires_debate": False,
        }

        self.result = SimpleNamespace(
            validation_id="validation_001",
            task_id="task_001",
        )

        self.results = {
            "validation_001": self.result,
        }

        self.validate_calls = []
        self.export_calls = []

    def validate_task(self, task_id):
        self.validate_calls.append(task_id)
        return self.result

    def get_result(self, validation_id):
        if validation_id not in self.results:
            raise KeyError(validation_id)

        return self.results[validation_id]

    def export_debate_payload(self, result):
        self.export_calls.append(result)
        return dict(self.payload)


class FakeDebateEngine:
    def __init__(self, debates=None):
        self.debates = debates or {}

    def get_debate(self, debate_id):
        if debate_id not in self.debates:
            raise KeyError(debate_id)

        return self.debates[debate_id]


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def task_manager():
    return FakeTaskManager()


@pytest.fixture
def validation_payload():
    return {
        "task_id": "task_001",
        "validation_id": "validation_001",
        "conflicts": [],
        "consensus": [
            {
                "description": (
                    "Operating cash flow should be monitored."
                )
            }
        ],
        "agent_analyses": [
            {"agent_id": "chatgpt"},
            {"agent_id": "grok"},
            {"agent_id": "hark"},
        ],
        "agreement_score": 0.85,
        "requires_debate": False,
    }


@pytest.fixture
def cross_validator(validation_payload):
    return FakeCrossValidator(
        payload=validation_payload,
    )


@pytest.fixture
def engine(
    task_manager,
    cross_validator,
    tmp_path,
):
    return ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=tmp_path / "consensus",
    )


@pytest.fixture
def unanimous_debate():
    return {
        "debate_id": "debate_001",
        "task_id": "task_001",
        "status": "completed",
        "participants": [
            "chatgpt",
            "grok",
            "hark",
        ],
        "rounds": [
            {
                "round_number": 1,
                "status": "completed",
                "messages": [
                    {
                        "message_id": "message_001",
                        "debate_id": "debate_001",
                        "round_number": 1,
                        "agent_id": "chatgpt",
                        "position": "support",
                        "content": (
                            "Revenue growth is supported by "
                            "verified order data.\n"
                            "CONFIDENCE: high"
                        ),
                        "evidence": [
                            "Annual report",
                            "Quarterly report",
                            "Company filing",
                        ],
                    },
                    {
                        "message_id": "message_002",
                        "debate_id": "debate_001",
                        "round_number": 1,
                        "agent_id": "grok",
                        "position": "support",
                        "content": (
                            "The industry demand trend supports "
                            "the research conclusion.\n"
                            "CONFIDENCE: high"
                        ),
                        "evidence": [
                            "Industry report",
                            "Company filing",
                        ],
                    },
                    {
                        "message_id": "message_003",
                        "debate_id": "debate_001",
                        "round_number": 1,
                        "agent_id": "hark",
                        "position": "support",
                        "content": (
                            "The current evidence supports the "
                            "research conclusion.\n"
                            "CONFIDENCE: medium"
                        ),
                        "evidence": [
                            "Financial report",
                        ],
                    },
                ],
            }
        ],
        "conclusion": "consensus",
        "conclusion_text": "All agents support the conclusion.",
        "unresolved_issues": [],
    }


@pytest.fixture
def split_debate():
    return {
        "debate_id": "debate_002",
        "task_id": "task_001",
        "status": "completed",
        "participants": [
            "chatgpt",
            "grok",
            "hark",
        ],
        "rounds": [
            {
                "round_number": 1,
                "status": "completed",
                "messages": [
                    {
                        "message_id": "message_101",
                        "debate_id": "debate_002",
                        "round_number": 1,
                        "agent_id": "chatgpt",
                        "position": "support",
                        "content": "Growth outlook is positive.",
                        "evidence": ["Source A"],
                    },
                    {
                        "message_id": "message_102",
                        "debate_id": "debate_002",
                        "round_number": 1,
                        "agent_id": "grok",
                        "position": "oppose",
                        "content": "Growth outlook is too optimistic.",
                        "evidence": ["Source B"],
                    },
                    {
                        "message_id": "message_103",
                        "debate_id": "debate_002",
                        "round_number": 1,
                        "agent_id": "hark",
                        "position": "oppose",
                        "content": "Risks outweigh current growth.",
                        "evidence": ["Source C"],
                    },
                ],
            }
        ],
        "conclusion": "no_consensus",
        "conclusion_text": "The agents disagree.",
        "unresolved_issues": [
            "Revenue forecast needs verification."
        ],
    }


# ============================================================
# Initialization tests
# ============================================================

def test_engine_initialization(
    task_manager,
    cross_validator,
    tmp_path,
):
    engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=tmp_path / "consensus",
    )

    assert engine.task_manager is task_manager
    assert engine.cross_validator is cross_validator
    assert engine.storage_dir.exists()
    assert engine.consensus_threshold == 0.67
    assert engine.evidence_threshold == 0.50


def test_engine_accepts_custom_thresholds(
    task_manager,
    cross_validator,
    tmp_path,
):
    engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=tmp_path,
        consensus_threshold=0.75,
        evidence_threshold=0.60,
    )

    assert engine.consensus_threshold == 0.75
    assert engine.evidence_threshold == 0.60


def test_engine_rejects_missing_task_manager(
    cross_validator,
    tmp_path,
):
    with pytest.raises(ValueError):
        ConsensusEngine(
            task_manager=None,
            cross_validator=cross_validator,
            storage_dir=tmp_path,
        )


def test_engine_rejects_missing_cross_validator(
    task_manager,
    tmp_path,
):
    with pytest.raises(ValueError):
        ConsensusEngine(
            task_manager=task_manager,
            cross_validator=None,
            storage_dir=tmp_path,
        )


@pytest.mark.parametrize(
    "threshold",
    [
        -0.1,
        1.1,
        "0.5",
        True,
    ],
)
def test_engine_rejects_invalid_consensus_threshold(
    task_manager,
    cross_validator,
    tmp_path,
    threshold,
):
    with pytest.raises(ValueError):
        ConsensusEngine(
            task_manager=task_manager,
            cross_validator=cross_validator,
            storage_dir=tmp_path,
            consensus_threshold=threshold,
        )


@pytest.mark.parametrize(
    "threshold",
    [
        -0.1,
        1.1,
        "0.5",
        True,
    ],
)
def test_engine_rejects_invalid_evidence_threshold(
    task_manager,
    cross_validator,
    tmp_path,
    threshold,
):
    with pytest.raises(ValueError):
        ConsensusEngine(
            task_manager=task_manager,
            cross_validator=cross_validator,
            storage_dir=tmp_path,
            evidence_threshold=threshold,
        )


# ============================================================
# Build consensus tests
# ============================================================

def test_build_consensus_returns_report(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert isinstance(report, ConsensusReport)
    assert report.task_id == "task_001"
    assert report.debate_id == "debate_001"


def test_build_consensus_generates_id(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.consensus_id.startswith("consensus_")


def test_build_consensus_uses_validation_payload(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.validation_id == "validation_001"
    assert report.consensus_points == [
        "Operating cash flow should be monitored."
    ]


def test_build_consensus_calls_validate_task_when_needed(
    engine,
    cross_validator,
):
    engine.build_consensus(
        task_id="task_001",
        force=True,
    )

    assert cross_validator.validate_calls == ["task_001"]


def test_build_consensus_uses_validation_id(
    engine,
    cross_validator,
    unanimous_debate,
):
    engine.build_consensus(
        task_id="task_001",
        validation_id="validation_001",
        debate=unanimous_debate,
    )

    assert cross_validator.validate_calls == []
    assert len(cross_validator.export_calls) == 1


def test_build_consensus_accepts_validation_mapping(
    engine,
    validation_payload,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        validation_result=validation_payload,
        debate=unanimous_debate,
    )

    assert report.validation_id == "validation_001"


def test_build_consensus_accepts_validation_object(
    engine,
    cross_validator,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        validation_result=cross_validator.result,
        debate=unanimous_debate,
    )

    assert report.validation_id == "validation_001"
    assert len(cross_validator.export_calls) == 1


def test_build_consensus_rejects_missing_task(engine):
    with pytest.raises(ConsensusTaskNotFoundError):
        engine.build_consensus(
            task_id="task_missing",
            force=True,
        )


def test_build_consensus_rejects_mismatched_task_id(
    engine,
    unanimous_debate,
):
    payload = {
        "task_id": "task_002",
        "conflicts": [],
        "consensus": [],
        "agent_analyses": [],
    }

    with pytest.raises(ConsensusValidationError):
        engine.build_consensus(
            task_id="task_001",
            validation_result=payload,
            debate=unanimous_debate,
        )


def test_build_consensus_requires_debate_when_flagged(
    engine,
    validation_payload,
):
    payload = dict(validation_payload)
    payload["requires_debate"] = True

    with pytest.raises(ConsensusDebateError):
        engine.build_consensus(
            task_id="task_001",
            validation_result=payload,
        )


def test_build_consensus_force_allows_missing_debate(
    engine,
    validation_payload,
):
    payload = dict(validation_payload)
    payload["requires_debate"] = True

    report = engine.build_consensus(
        task_id="task_001",
        validation_result=payload,
        force=True,
    )

    assert report.debate_id is None
    assert report.status == ConsensusStatus.INSUFFICIENT_EVIDENCE.value


def test_build_consensus_rejects_unknown_debate_id(
    engine,
):
    with pytest.raises(ConsensusDebateError):
        engine.build_consensus(
            task_id="task_001",
            debate_id="debate_001",
        )


def test_build_consensus_rejects_debate_and_debate_id_together(
    engine,
    unanimous_debate,
):
    with pytest.raises(ConsensusDebateError):
        engine.build_consensus(
            task_id="task_001",
            debate=unanimous_debate,
            debate_id="debate_001",
        )


def test_build_consensus_rejects_invalid_conflicts_type(
    engine,
    unanimous_debate,
):
    payload = {
        "task_id": "task_001",
        "conflicts": "invalid",
        "consensus": [],
        "agent_analyses": [],
    }

    with pytest.raises(ConsensusValidationError):
        engine.build_consensus(
            task_id="task_001",
            validation_result=payload,
            debate=unanimous_debate,
        )


def test_build_consensus_rejects_invalid_consensus_type(
    engine,
    unanimous_debate,
):
    payload = {
        "task_id": "task_001",
        "conflicts": [],
        "consensus": "invalid",
        "agent_analyses": [],
    }

    with pytest.raises(ConsensusValidationError):
        engine.build_consensus(
            task_id="task_001",
            validation_result=payload,
            debate=unanimous_debate,
        )


# ============================================================
# Participant tests
# ============================================================

def test_build_consensus_detects_participants(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.participants == [
        "chatgpt",
        "grok",
        "hark",
    ]


def test_build_consensus_accepts_custom_participants(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
        participants=["chatgpt", "grok"],
    )

    assert report.participants == ["chatgpt", "grok"]
    assert len(report.votes) == 2


def test_build_consensus_deduplicates_participants(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
        participants=[
            "chatgpt",
            "grok",
            "chatgpt",
        ],
    )

    assert report.participants == [
        "chatgpt",
        "grok",
    ]


def test_build_consensus_rejects_unknown_participant(
    engine,
    unanimous_debate,
):
    with pytest.raises(ConsensusValidationError):
        engine.build_consensus(
            task_id="task_001",
            debate=unanimous_debate,
            participants=["chatgpt", "unknown"],
        )


def test_build_consensus_uses_validation_agents_without_debate(
    engine,
):
    report = engine.build_consensus(
        task_id="task_001",
        force=True,
    )

    assert report.participants == [
        "chatgpt",
        "grok",
        "hark",
    ]


# ============================================================
# Agent vote tests
# ============================================================

def test_build_votes_from_debate(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert len(report.votes) == 3

    assert [
        vote.position
        for vote in report.votes
    ] == [
        "support",
        "support",
        "support",
    ]


def test_vote_records_latest_response(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    chatgpt_vote = report.votes[0]

    assert "Revenue growth" in chatgpt_vote.latest_response
    assert chatgpt_vote.source_round == 1


def test_vote_counts_evidence(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.votes[0].evidence_count == 3
    assert report.votes[1].evidence_count == 2
    assert report.votes[2].evidence_count == 1


def test_vote_assigns_evidence_strength(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.votes[0].evidence_strength == (
        EvidenceStrength.STRONG.value
    )

    assert report.votes[1].evidence_strength == (
        EvidenceStrength.MODERATE.value
    )

    assert report.votes[2].evidence_strength == (
        EvidenceStrength.MODERATE.value
    )


def test_vote_extracts_confidence_text(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.votes[0].confidence_text == "high"
    assert report.votes[2].confidence_text == "medium"


def test_vote_uses_latest_round_position(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["rounds"] = [
        {
            "round_number": 1,
            "messages": [
                {
                    "agent_id": "chatgpt",
                    "position": "support",
                    "content": "First round.",
                    "evidence": ["Source A"],
                }
            ],
        },
        {
            "round_number": 2,
            "messages": [
                {
                    "agent_id": "chatgpt",
                    "position": "oppose",
                    "content": "Second round changed my view.",
                    "evidence": ["Source B"],
                }
            ],
        },
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
        participants=["chatgpt", "grok"],
    )

    assert report.votes[0].position == "oppose"
    assert "Second round" in report.votes[0].latest_response


def test_missing_agent_vote_is_unknown(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["rounds"] = [
        {
            "round_number": 1,
            "messages": [
                {
                    "agent_id": "chatgpt",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": ["Source A"],
                }
            ],
        }
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    hark_vote = next(
        vote
        for vote in report.votes
        if vote.agent_id == "hark"
    )

    assert hark_vote.position == AgentPosition.UNKNOWN.value
    assert hark_vote.evidence_count == 0


# ============================================================
# Agreement and evidence score tests
# ============================================================

def test_unanimous_positions_have_full_agreement(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.position_agreement == 1.0


def test_split_positions_calculate_agreement(
    engine,
    split_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=split_debate,
    )

    assert report.position_agreement == pytest.approx(2 / 3)


def test_missing_vote_reduces_position_agreement(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["rounds"] = [
        {
            "round_number": 1,
            "messages": [
                {
                    "agent_id": "chatgpt",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": ["Source A"],
                },
                {
                    "agent_id": "grok",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": ["Source B"],
                },
            ],
        }
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert report.position_agreement == pytest.approx(2 / 3)


def test_all_agents_with_evidence_have_full_evidence_score(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.evidence_score == 1.0


def test_missing_evidence_reduces_evidence_score(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["rounds"] = [
        {
            "round_number": 1,
            "messages": [
                {
                    "agent_id": "chatgpt",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": ["Source A"],
                },
                {
                    "agent_id": "grok",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": [],
                },
                {
                    "agent_id": "hark",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": [],
                },
            ],
        }
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert report.evidence_score == pytest.approx(1 / 3)


# ============================================================
# Consensus status tests
# ============================================================

def test_unanimous_supported_positions_reach_consensus(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.status == ConsensusStatus.CONSENSUS.value


def test_split_positions_produce_no_consensus(
    engine,
    split_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=split_debate,
    )

    assert report.status == ConsensusStatus.NO_CONSENSUS.value


def test_unresolved_issues_produce_partial_consensus(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["unresolved_issues"] = [
        "Revenue forecast needs further verification."
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert report.status == ConsensusStatus.PARTIAL_CONSENSUS.value


def test_validation_conflicts_produce_partial_consensus(
    engine,
    unanimous_debate,
):
    payload = {
        "task_id": "task_001",
        "validation_id": "validation_001",
        "conflicts": [
            {
                "description": "Gross margin estimates differ.",
                "severity": "high",
            }
        ],
        "consensus": [],
        "agent_analyses": [
            {"agent_id": "chatgpt"},
            {"agent_id": "grok"},
            {"agent_id": "hark"},
        ],
        "agreement_score": 0.90,
        "requires_debate": False,
    }

    report = engine.build_consensus(
        task_id="task_001",
        validation_result=payload,
        debate=unanimous_debate,
    )

    assert report.status == ConsensusStatus.PARTIAL_CONSENSUS.value
    assert len(report.issues) == 1


def test_insufficient_evidence_produces_low_confidence(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["rounds"] = [
        {
            "round_number": 1,
            "messages": [
                {
                    "agent_id": "chatgpt",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": [],
                },
                {
                    "agent_id": "grok",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": [],
                },
                {
                    "agent_id": "hark",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": [],
                },
            ],
        }
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert (
        report.status
        == ConsensusStatus.INSUFFICIENT_EVIDENCE.value
    )

    assert report.confidence == ConfidenceLevel.LOW.value


def test_unknown_positions_produce_insufficient_evidence(
    engine,
):
    debate = {
        "debate_id": "debate_unknown",
        "task_id": "task_001",
        "participants": ["chatgpt", "grok"],
        "rounds": [
            {
                "round_number": 1,
                "messages": [
                    {
                        "agent_id": "chatgpt",
                        "position": "clarify",
                        "content": "Need clarification.",
                        "evidence": ["Source A"],
                    },
                    {
                        "agent_id": "grok",
                        "position": "unknown",
                        "content": "No position.",
                        "evidence": ["Source B"],
                    },
                ],
            }
        ],
    }

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
        participants=["chatgpt", "grok"],
    )

    assert (
        report.status
        == ConsensusStatus.INSUFFICIENT_EVIDENCE.value
    )


def test_debate_consensus_does_not_override_split_votes(
    engine,
    split_debate,
):
    debate = dict(split_debate)
    debate["conclusion"] = "consensus"

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert report.status == ConsensusStatus.NO_CONSENSUS.value


def test_debate_partial_consensus_is_preserved(
    engine,
    split_debate,
):
    debate = dict(split_debate)
    debate["conclusion"] = "partial_consensus"

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert (
        report.status
        == ConsensusStatus.PARTIAL_CONSENSUS.value
    )


def test_consensus_threshold_can_be_configured(
    task_manager,
    cross_validator,
    unanimous_debate,
    tmp_path,
):
    custom_engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=tmp_path / "custom",
        consensus_threshold=0.90,
    )

    report = custom_engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.status == ConsensusStatus.CONSENSUS.value


# ============================================================
# Confidence tests
# ============================================================

def test_unanimous_evidence_supported_result_has_high_confidence(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.confidence == ConfidenceLevel.HIGH.value


def test_no_consensus_has_not_high_confidence(
    engine,
    split_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=split_debate,
    )

    assert report.confidence != ConfidenceLevel.HIGH.value


def test_confidence_uses_validation_agreement_score(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        validation_result={
            "task_id": "task_001",
            "validation_id": "validation_low",
            "conflicts": [],
            "consensus": [],
            "agent_analyses": [
                {"agent_id": "chatgpt"},
                {"agent_id": "grok"},
                {"agent_id": "hark"},
            ],
            "agreement_score": 0.20,
            "requires_debate": False,
        },
        debate=unanimous_debate,
    )

    assert report.agreement_score == 0.20
    assert report.confidence != ConfidenceLevel.HIGH.value


# ============================================================
# Issues and unresolved issue tests
# ============================================================

def test_validation_conflicts_become_issues(
    engine,
    unanimous_debate,
):
    payload = {
        "task_id": "task_001",
        "validation_id": "validation_001",
        "conflicts": [
            {
                "description": "Revenue growth estimates differ.",
                "severity": "high",
                "category": "financial",
            },
            {
                "description": "Market outlook is uncertain.",
                "severity": "medium",
                "category": "market",
            },
        ],
        "consensus": [],
        "agent_analyses": [
            {"agent_id": "chatgpt"},
            {"agent_id": "grok"},
            {"agent_id": "hark"},
        ],
        "agreement_score": 0.70,
        "requires_debate": False,
    }

    report = engine.build_consensus(
        task_id="task_001",
        validation_result=payload,
        debate=unanimous_debate,
    )

    assert len(report.issues) == 2
    assert report.issues[0].severity == "high"
    assert report.issues[0].category == "financial"


def test_debate_unresolved_issues_become_issues(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["unresolved_issues"] = [
        "Capital expenditure assumptions need verification."
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert any(
        issue.source == "debate"
        for issue in report.issues
    )


def test_unresolved_issues_are_deduplicated(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["unresolved_issues"] = [
        "Revenue forecast needs verification.",
        "Revenue forecast needs verification.",
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert report.unresolved_issues == [
        "Revenue forecast needs verification."
    ]


def test_consensus_points_are_deduplicated(
    engine,
    validation_payload,
    unanimous_debate,
):
    payload = dict(validation_payload)
    payload["consensus"] = [
        "Cash flow should be monitored.",
        "Cash flow should be monitored.",
    ]

    debate = dict(unanimous_debate)
    debate["consensus_points"] = [
        "Cash flow should be monitored.",
        "Order visibility should be monitored.",
    ]

    report = engine.build_consensus(
        task_id="task_001",
        validation_result=payload,
        debate=debate,
    )

    assert report.consensus_points == [
        "Cash flow should be monitored.",
        "Order visibility should be monitored.",
    ]


# ============================================================
# Risk warning tests
# ============================================================

def test_no_consensus_generates_warning(
    engine,
    split_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=split_debate,
    )

    assert any(
        "未形成共识" in warning
        for warning in report.risk_warnings
    )


def test_missing_evidence_generates_warning(
    engine,
    unanimous_debate,
):
    debate = dict(unanimous_debate)
    debate["rounds"] = [
        {
            "round_number": 1,
            "messages": [
                {
                    "agent_id": "chatgpt",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": ["Source A"],
                },
                {
                    "agent_id": "grok",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": [],
                },
                {
                    "agent_id": "hark",
                    "position": "support",
                    "content": "Supported.",
                    "evidence": [],
                },
            ],
        }
    ]

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert any(
        "未提供证据引用" in warning
        for warning in report.risk_warnings
    )


def test_missing_agent_generates_warning(
    engine,
):
    debate = {
        "debate_id": "debate_missing",
        "task_id": "task_001",
        "participants": [
            "chatgpt",
            "grok",
            "hark",
        ],
        "rounds": [
            {
                "round_number": 1,
                "messages": [
                    {
                        "agent_id": "chatgpt",
                        "position": "support",
                        "content": "Supported.",
                        "evidence": ["Source A"],
                    },
                    {
                        "agent_id": "grok",
                        "position": "support",
                        "content": "Supported.",
                        "evidence": ["Source B"],
                    },
                ],
            }
        ],
    }

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
    )

    assert any(
        "hark" in warning
        for warning in report.risk_warnings
    )


def test_validation_debate_flag_generates_warning(
    engine,
    unanimous_debate,
):
    payload = {
        "task_id": "task_001",
        "validation_id": "validation_001",
        "conflicts": [],
        "consensus": [],
        "agent_analyses": [
            {"agent_id": "chatgpt"},
            {"agent_id": "grok"},
            {"agent_id": "hark"},
        ],
        "agreement_score": 0.85,
        "requires_debate": True,
    }

    report = engine.build_consensus(
        task_id="task_001",
        validation_result=payload,
        debate=unanimous_debate,
    )

    assert any(
        "需要辩论" in warning
        for warning in report.risk_warnings
    )


# ============================================================
# Debate engine integration tests
# ============================================================

def test_build_consensus_loads_debate_by_id(
    task_manager,
    cross_validator,
    unanimous_debate,
    tmp_path,
):
    fake_debate_engine = FakeDebateEngine(
        debates={
            "debate_001": unanimous_debate,
        }
    )

    consensus_engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        debate_engine=fake_debate_engine,
        storage_dir=tmp_path / "consensus",
    )

    report = consensus_engine.build_consensus(
        task_id="task_001",
        debate_id="debate_001",
    )

    assert report.debate_id == "debate_001"
    assert report.status == ConsensusStatus.CONSENSUS.value


def test_build_consensus_accepts_debate_session_like_object(
    engine,
    unanimous_debate,
):
    debate_object = SimpleNamespace(
        debate_id=unanimous_debate["debate_id"],
        task_id=unanimous_debate["task_id"],
        status=unanimous_debate["status"],
        participants=unanimous_debate["participants"],
        rounds=[
            SimpleNamespace(
                round_number=1,
                messages=[
                    SimpleNamespace(**message)
                    for message in unanimous_debate[
                        "rounds"
                    ][0]["messages"]
                ],
            )
        ],
        conclusion=unanimous_debate["conclusion"],
        conclusion_text=unanimous_debate["conclusion_text"],
        unresolved_issues=[],
    )

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate_object,
    )

    assert report.debate_id == "debate_001"
    assert report.position_agreement == 1.0


def test_build_consensus_records_debate_metadata(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert report.metadata["debate_status"] == "completed"
    assert report.metadata["debate_conclusion"] == "consensus"


# ============================================================
# Retrieval and listing tests
# ============================================================

def test_get_report_returns_saved_report(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    loaded = engine.get_report(report.consensus_id)

    assert loaded.consensus_id == report.consensus_id
    assert loaded.task_id == "task_001"


def test_get_report_rejects_missing_id(engine):
    with pytest.raises(ConsensusNotFoundError):
        engine.get_report("consensus_missing")


def test_list_reports_returns_summaries(
    engine,
    unanimous_debate,
):
    engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    summaries = engine.list_reports()

    assert len(summaries) == 1
    assert summaries[0].task_id == "task_001"
    assert summaries[0].participant_count == 3


def test_list_reports_filters_by_task(
    engine,
    unanimous_debate,
):
    engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    assert engine.list_reports(task_id="task_002") == []


def test_list_reports_filters_by_status(
    engine,
    unanimous_debate,
):
    engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    reports = engine.list_reports(
        status="consensus",
    )

    assert len(reports) == 1

    assert engine.list_reports(
        status="no_consensus",
    ) == []


def test_list_reports_rejects_invalid_status(engine):
    with pytest.raises(ValueError):
        engine.list_reports(status="invalid")


# ============================================================
# Persistence tests
# ============================================================

def test_build_consensus_creates_json_file(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    path = (
        engine.storage_dir
        / f"consensus_{report.consensus_id.split('consensus_', 1)[-1]}.json"
    )

    assert path.exists()


def test_save_report_returns_path(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    path = engine.save_report(report)

    assert isinstance(path, Path)
    assert path.exists()


def test_saved_report_is_valid_json(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    path = engine.save_report(report)

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    assert data["consensus_id"] == report.consensus_id
    assert data["task_id"] == "task_001"
    assert data["status"] == "consensus"


def test_new_engine_can_load_saved_report(
    task_manager,
    cross_validator,
    unanimous_debate,
    tmp_path,
):
    storage_dir = tmp_path / "consensus"

    first_engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    report = first_engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    second_engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    loaded = second_engine.get_report(
        report.consensus_id
    )

    assert loaded.consensus_id == report.consensus_id
    assert loaded.status == report.status
    assert len(loaded.votes) == 3


def test_new_engine_can_list_saved_reports(
    task_manager,
    cross_validator,
    unanimous_debate,
    tmp_path,
):
    storage_dir = tmp_path / "consensus"

    first_engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    first_engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    second_engine = ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    summaries = second_engine.list_reports()

    assert len(summaries) == 1


# ============================================================
# Export tests
# ============================================================

def test_export_report_returns_dictionary(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    exported = engine.export_report(
        report.consensus_id
    )

    assert isinstance(exported, dict)
    assert exported["consensus_id"] == report.consensus_id


def test_export_report_contains_votes(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    exported = engine.export_report(
        report.consensus_id
    )

    assert len(exported["votes"]) == 3
    assert exported["votes"][0]["agent_id"] == "chatgpt"


def test_export_markdown_contains_header(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    markdown = engine.export_markdown(
        report.consensus_id
    )

    assert "# AI Team Consensus Report" in markdown
    assert report.consensus_id in markdown
    assert "## Final conclusion" in markdown


def test_export_markdown_contains_positions(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    markdown = engine.export_markdown(
        report.consensus_id
    )

    assert "### chatgpt" in markdown
    assert "### grok" in markdown
    assert "### hark" in markdown
    assert "support" in markdown


def test_export_markdown_contains_methodology_note(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    markdown = engine.export_markdown(
        report.consensus_id
    )

    assert "does not independently verify" in markdown


# ============================================================
# Data model tests
# ============================================================

def test_agent_consensus_vote_to_dict():
    vote = AgentConsensusVote(
        agent_id="chatgpt",
        position="support",
        response_count=2,
        evidence_count=3,
        evidence_strength="strong",
    )

    data = vote.to_dict()

    assert data["agent_id"] == "chatgpt"
    assert data["position"] == "support"
    assert data["evidence_count"] == 3


def test_consensus_issue_to_dict():
    issue = ConsensusIssue(
        issue_id="issue_001",
        category="financial",
        description="Revenue estimates differ.",
        severity="high",
    )

    data = issue.to_dict()

    assert data["issue_id"] == "issue_001"
    assert data["category"] == "financial"
    assert data["resolved"] is False


def test_consensus_report_to_dict(
    engine,
    unanimous_debate,
):
    report = engine.build_consensus(
        task_id="task_001",
        debate=unanimous_debate,
    )

    data = report.to_dict()

    assert data["consensus_id"] == report.consensus_id
    assert data["status"] == report.status
    assert isinstance(data["votes"], list)
    assert isinstance(data["issues"], list)


# ============================================================
# Boundary and regression tests
# ============================================================

def test_task_id_rejects_path_traversal(engine):
    with pytest.raises(ValueError):
        engine.build_consensus(
            task_id="../outside",
            force=True,
        )


def test_consensus_id_rejects_path_traversal(engine):
    with pytest.raises(ValueError):
        engine.get_report("../outside")


def test_invalid_debate_rounds_type_is_rejected(
    engine,
):
    debate = {
        "debate_id": "debate_invalid",
        "task_id": "task_001",
        "participants": ["chatgpt", "grok"],
        "rounds": "invalid",
    }

    with pytest.raises(ConsensusDebateError):
        engine.build_consensus(
            task_id="task_001",
            debate=debate,
        )


def test_invalid_debate_unresolved_issues_type_is_rejected(
    engine,
):
    debate = {
        "debate_id": "debate_invalid",
        "task_id": "task_001",
        "participants": ["chatgpt", "grok"],
        "rounds": [],
        "unresolved_issues": "invalid",
    }

    with pytest.raises(ConsensusDebateError):
        engine.build_consensus(
            task_id="task_001",
            debate=debate,
        )


def test_chinese_content_is_preserved(
    engine,
):
    debate = {
        "debate_id": "debate_chinese",
        "task_id": "task_001",
        "participants": ["chatgpt", "grok"],
        "rounds": [
            {
                "round_number": 1,
                "messages": [
                    {
                        "agent_id": "chatgpt",
                        "position": "support",
                        "content": "公司现金流改善，支持当前研究判断。",
                        "evidence": ["公司年度报告"],
                    },
                    {
                        "agent_id": "grok",
                        "position": "support",
                        "content": "行业需求趋势提供了支持。",
                        "evidence": ["行业研究报告"],
                    },
                ],
            }
        ],
    }

    report = engine.build_consensus(
        task_id="task_001",
        debate=debate,
        participants=["chatgpt", "grok"],
    )

    assert "公司现金流改善" in report.votes[0].latest_response

    path = engine.save_report(report)
    raw_text = path.read_text(encoding="utf-8")

    assert "公司现金流改善" in raw_text


def test_consensus_engine_has_no_trade_execution_api():
    public_methods = {
        name
        for name in dir(ConsensusEngine)
        if not name.startswith("_")
    }

    forbidden_names = {
        "place_order",
        "submit_order",
        "execute_trade",
        "buy_stock",
        "sell_stock",
        "connect_broker",
    }

    assert public_methods.isdisjoint(forbidden_names)


# ============================================================
# End of test suite
# ============================================================
