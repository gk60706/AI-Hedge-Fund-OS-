import json

from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_team.debate_engine import (
    DebateEngine,
    MAX_ALLOWED_ROUNDS,
    DebateEngineError,
    DebateTaskNotFoundError,
    DebateNotRequiredError,
    DebateNotFoundError,
    DebateStateError,
    DebateParticipantError,
    DebateResponseError,
    DebatePersistenceError,
    DebateStatus,
    DebateRoundStatus,
    DebatePosition,
    DebateConclusion,
    DebateMessage,
    DebateRound,
    DebateSession,
)


# ============================================================
# Fake dependencies
# ============================================================

class FakeTaskManager:
    def __init__(self, tasks=None):
        self.tasks = tasks or {}

    def get_task(self, task_id):
        return self.tasks.get(task_id)


class FakeCrossValidator:
    def __init__(
        self,
        payload=None,
        result=None,
    ):
        self.payload = payload or {
            "task_id": "task_001",
            "validation_id": "validation_001",
            "conflicts": [
                {
                    "description": (
                        "Agents disagree about revenue growth."
                    )
                }
            ],
            "consensus": [
                {
                    "description": (
                        "All agents agree that cash flow "
                        "should be monitored."
                    )
                }
            ],
            "agent_analyses": [
                {"agent_id": "chatgpt"},
                {"agent_id": "grok"},
                {"agent_id": "hark"},
            ],
            "agreement_score": 0.62,
            "requires_debate": True,
        }

        self.result = result or SimpleNamespace(
            validation_id="validation_001",
            task_id="task_001",
        )

        self.validate_calls = []
        self.export_calls = []
        self.results = {
            "validation_001": self.result,
        }

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


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def task_manager():
    return FakeTaskManager(
        tasks={
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
    )


@pytest.fixture
def validation_payload():
    return {
        "task_id": "task_001",
        "validation_id": "validation_001",
        "conflicts": [
            {
                "description": (
                    "The agents disagree on the sustainability "
                    "of revenue growth."
                ),
                "severity": "high",
            },
            {
                "description": (
                    "The agents have different estimates "
                    "of gross margin."
                ),
                "severity": "medium",
            },
        ],
        "consensus": [
            {
                "description": (
                    "All agents agree that operating cash flow "
                    "is an important monitoring indicator."
                )
            }
        ],
        "agent_analyses": [
            {"agent_id": "chatgpt"},
            {"agent_id": "grok"},
            {"agent_id": "hark"},
        ],
        "agreement_score": 0.58,
        "requires_debate": True,
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
    return DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=tmp_path / "debates",
    )


@pytest.fixture
def debate(engine):
    return engine.start_debate(
        task_id="task_001",
    )


# ============================================================
# Initialization tests
# ============================================================

def test_engine_initialization(
    task_manager,
    cross_validator,
    tmp_path,
):
    engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=tmp_path / "debates",
    )

    assert engine.task_manager is task_manager
    assert engine.cross_validator is cross_validator
    assert engine.storage_dir.exists()
    assert engine.default_max_rounds == 2


def test_engine_accepts_custom_max_rounds(
    task_manager,
    cross_validator,
    tmp_path,
):
    engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=tmp_path / "debates",
        default_max_rounds=4,
    )

    assert engine.default_max_rounds == 4


def test_engine_rejects_missing_task_manager(
    cross_validator,
    tmp_path,
):
    with pytest.raises(ValueError):
        DebateEngine(
            task_manager=None,
            cross_validator=cross_validator,
            storage_dir=tmp_path,
        )


def test_engine_rejects_missing_cross_validator(
    task_manager,
    tmp_path,
):
    with pytest.raises(ValueError):
        DebateEngine(
            task_manager=task_manager,
            cross_validator=None,
            storage_dir=tmp_path,
        )


def test_engine_rejects_invalid_default_max_rounds(
    task_manager,
    cross_validator,
    tmp_path,
):
    with pytest.raises(ValueError):
        DebateEngine(
            task_manager=task_manager,
            cross_validator=cross_validator,
            storage_dir=tmp_path,
            default_max_rounds=0,
        )


def test_engine_rejects_excessive_default_max_rounds(
    task_manager,
    cross_validator,
    tmp_path,
):
    with pytest.raises(ValueError):
        DebateEngine(
            task_manager=task_manager,
            cross_validator=cross_validator,
            storage_dir=tmp_path,
            default_max_rounds=11,
        )


def test_engine_rejects_non_integer_default_max_rounds(
    task_manager,
    cross_validator,
    tmp_path,
):
    with pytest.raises(TypeError):
        DebateEngine(
            task_manager=task_manager,
            cross_validator=cross_validator,
            storage_dir=tmp_path,
            default_max_rounds=2.5,
        )


# ============================================================
# Start debate tests
# ============================================================

def test_start_debate_creates_session(debate):
    assert isinstance(debate, DebateSession)
    assert debate.task_id == "task_001"
    assert debate.status == DebateStatus.IN_PROGRESS.value
    assert debate.current_round == 1
    assert debate.max_rounds == 2


def test_start_debate_generates_id(debate):
    assert debate.debate_id.startswith("debate_")
    assert len(debate.debate_id) > len("debate_")


def test_start_debate_detects_participants(debate):
    assert debate.participants == [
        "chatgpt",
        "grok",
        "hark",
    ]


def test_start_debate_creates_first_round(debate):
    assert len(debate.rounds) == 1

    first_round = debate.rounds[0]

    assert first_round.round_number == 1
    assert first_round.status == DebateRoundStatus.OPEN.value
    assert "ROUND 1" in first_round.prompt


def test_start_debate_includes_conflicts_in_prompt(debate):
    prompt = debate.rounds[0].prompt

    assert "revenue growth" in prompt
    assert "gross margin" in prompt


def test_start_debate_includes_consensus_in_prompt(debate):
    prompt = debate.rounds[0].prompt

    assert "operating cash flow" in prompt


def test_start_debate_includes_response_format(debate):
    prompt = debate.rounds[0].prompt

    assert "POSITION:" in prompt
    assert "CORE_ARGUMENT:" in prompt
    assert "EVIDENCE:" in prompt
    assert "CONFIDENCE:" in prompt


def test_start_debate_calls_validation_when_result_missing(
    engine,
    cross_validator,
):
    engine.start_debate(
        task_id="task_001",
    )

    assert cross_validator.validate_calls == ["task_001"]


def test_start_debate_uses_existing_validation_id(
    engine,
    cross_validator,
):
    engine.start_debate(
        task_id="task_001",
        validation_id="validation_001",
    )

    assert cross_validator.validate_calls == []
    assert len(cross_validator.export_calls) == 1


def test_start_debate_accepts_validation_payload_mapping(
    engine,
    validation_payload,
    cross_validator,
):
    session = engine.start_debate(
        task_id="task_001",
        validation_result=validation_payload,
    )

    assert session.validation_id == "validation_001"
    assert session.task_id == "task_001"
    assert cross_validator.export_calls == []


def test_start_debate_rejects_missing_task(
    engine,
):
    with pytest.raises(DebateTaskNotFoundError):
        engine.start_debate(
            task_id="task_missing",
        )


def test_start_debate_rejects_mismatched_task_id(
    engine,
):
    payload = {
        "task_id": "task_002",
        "validation_id": "validation_002",
        "conflicts": [],
        "consensus": [],
        "agent_analyses": [
            {"agent_id": "chatgpt"},
            {"agent_id": "grok"},
        ],
        "requires_debate": True,
    }

    with pytest.raises(DebateEngineError):
        engine.start_debate(
            task_id="task_001",
            validation_result=payload,
        )


def test_start_debate_rejects_when_debate_not_required(
    engine,
    validation_payload,
):
    payload = dict(validation_payload)
    payload["requires_debate"] = False

    with pytest.raises(DebateNotRequiredError):
        engine.start_debate(
            task_id="task_001",
            validation_result=payload,
        )


def test_start_debate_can_be_forced(
    engine,
    validation_payload,
):
    payload = dict(validation_payload)
    payload["requires_debate"] = False

    session = engine.start_debate(
        task_id="task_001",
        validation_result=payload,
        force=True,
    )

    assert session.status == DebateStatus.IN_PROGRESS.value


def test_start_debate_accepts_custom_participants(
    engine,
    validation_payload,
):
    session = engine.start_debate(
        task_id="task_001",
        validation_result=validation_payload,
        participants=["chatgpt", "grok"],
    )

    assert session.participants == ["chatgpt", "grok"]


def test_start_debate_removes_duplicate_participants(
    engine,
    validation_payload,
):
    session = engine.start_debate(
        task_id="task_001",
        validation_result=validation_payload,
        participants=[
            "chatgpt",
            "grok",
            "chatgpt",
        ],
    )

    assert session.participants == ["chatgpt", "grok"]


def test_start_debate_rejects_single_participant(
    engine,
    validation_payload,
):
    with pytest.raises(DebateParticipantError):
        engine.start_debate(
            task_id="task_001",
            validation_result=validation_payload,
            participants=["chatgpt"],
        )


def test_start_debate_rejects_unknown_participant(
    engine,
    validation_payload,
):
    with pytest.raises(DebateParticipantError):
        engine.start_debate(
            task_id="task_001",
            validation_result=validation_payload,
            participants=["chatgpt", "unknown"],
        )


def test_start_debate_rejects_invalid_max_rounds(
    engine,
):
    with pytest.raises(ValueError):
        engine.start_debate(
            task_id="task_001",
            max_rounds=0,
        )


def test_start_debate_rejects_too_many_rounds(
    engine,
):
    with pytest.raises(ValueError):
        engine.start_debate(
            task_id="task_001",
            max_rounds=MAX_ALLOWED_ROUNDS + 1,
        )


# ============================================================
# Response submission tests
# ============================================================

def test_submit_response_creates_message(
    engine,
    debate,
):
    message = engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        position="support",
        content="Revenue growth is supported by order data.",
        evidence=[
            "Latest company filing",
            "Quarterly order data",
        ],
    )

    assert isinstance(message, DebateMessage)
    assert message.agent_id == "chatgpt"
    assert message.position == DebatePosition.SUPPORT.value
    assert len(message.evidence) == 2


def test_submit_response_uses_current_round(
    engine,
    debate,
):
    message = engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="grok",
        content="I disagree with the revenue forecast.",
    )

    assert message.round_number == 1


def test_submit_response_normalizes_agent_id(
    engine,
    debate,
):
    message = engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="GROK",
        content="I need additional evidence.",
    )

    assert message.agent_id == "grok"


def test_submit_response_normalizes_position(
    engine,
    debate,
):
    message = engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        position="SUPPORT",
        content="Supported.",
    )

    assert message.position == "support"


def test_submit_response_rejects_empty_content(
    engine,
    debate,
):
    with pytest.raises(ValueError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="   ",
        )


def test_submit_response_rejects_unknown_agent(
    engine,
    debate,
):
    with pytest.raises(DebateParticipantError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="unknown",
            content="Some response.",
        )


def test_submit_response_rejects_non_participant(
    engine,
    debate,
):
    with pytest.raises(DebateParticipantError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="hark",
            content="Some response.",
        ) if debate.participants == ["chatgpt", "grok"] else (
            engine.submit_response(
                debate_id=debate.debate_id,
                agent_id="unknown",
                content="Some response.",
            )
        )


def test_submit_response_rejects_duplicate_submission(
    engine,
    debate,
):
    engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        content="First response.",
    )

    with pytest.raises(DebateResponseError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="Second response.",
        )


def test_submit_response_rejects_invalid_position(
    engine,
    debate,
):
    with pytest.raises(DebateResponseError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            position="buy",
            content="Invalid position.",
        )


def test_submit_response_rejects_wrong_round_number(
    engine,
    debate,
):
    with pytest.raises(DebateResponseError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="Wrong round.",
            round_number=2,
        )


def test_submit_response_deduplicates_evidence(
    engine,
    debate,
):
    message = engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        content="Evidence is available.",
        evidence=[
            "Annual report",
            "Annual report",
            "Quarterly report",
        ],
    )

    assert message.evidence == [
        "Annual report",
        "Quarterly report",
    ]


def test_submit_response_rejects_invalid_evidence_item(
    engine,
    debate,
):
    with pytest.raises(ValueError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="Response.",
            evidence=[""],
        )


def test_submit_response_persists_message(
    engine,
    debate,
):
    engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        content="Response persisted.",
    )

    loaded = engine.get_debate(debate.debate_id)

    assert len(loaded.rounds[0].messages) == 1
    assert (
        loaded.rounds[0].messages[0].content
        == "Response persisted."
    )


# ============================================================
# Advance round tests
# ============================================================

def submit_all_participants(engine, debate):
    for agent_id in debate.participants:
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id=agent_id,
            position="neutral",
            content=f"{agent_id} completed the analysis.",
            evidence=[f"{agent_id} supporting evidence"],
        )


def test_advance_round_requires_all_responses(
    engine,
    debate,
):
    engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        content="ChatGPT response.",
    )

    with pytest.raises(DebateStateError):
        engine.advance_round(debate.debate_id)


def test_advance_round_can_allow_incomplete_responses(
    engine,
    debate,
):
    engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        content="ChatGPT response.",
    )

    next_round = engine.advance_round(
        debate.debate_id,
        allow_incomplete=True,
    )

    assert next_round.round_number == 2
    assert next_round.status == DebateRoundStatus.OPEN.value


def test_advance_round_completes_previous_round(
    engine,
    debate,
):
    submit_all_participants(engine, debate)

    engine.advance_round(debate.debate_id)

    loaded = engine.get_debate(debate.debate_id)

    assert (
        loaded.rounds[0].status
        == DebateRoundStatus.COMPLETED.value
    )


def test_advance_round_creates_follow_up_prompt(
    engine,
    debate,
):
    submit_all_participants(engine, debate)

    next_round = engine.advance_round(debate.debate_id)

    assert "ROUND 2" in next_round.prompt
    assert "ChatGPT" not in next_round.prompt
    assert "completed the analysis" in next_round.prompt


def test_advance_round_updates_current_round(
    engine,
    debate,
):
    submit_all_participants(engine, debate)

    engine.advance_round(debate.debate_id)

    loaded = engine.get_debate(debate.debate_id)

    assert loaded.current_round == 2
    assert len(loaded.rounds) == 2


def test_advance_round_rejects_completed_debate(
    engine,
    debate,
):
    submit_all_participants(engine, debate)

    engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="partial_consensus",
        conclusion_text="The debate is complete.",
    )

    with pytest.raises(DebateStateError):
        engine.advance_round(debate.debate_id)


def test_advance_round_rejects_maximum_rounds(
    engine,
    debate,
):
    submit_all_participants(engine, debate)

    engine.advance_round(debate.debate_id)

    submit_all_participants(engine, debate)

    with pytest.raises(DebateStateError):
        engine.advance_round(debate.debate_id)

    loaded = engine.get_debate(debate.debate_id)

    assert loaded.current_round == 2
    assert (
        loaded.rounds[1].status
        == DebateRoundStatus.COMPLETED.value
    )


# ============================================================
# Finalize tests
# ============================================================

@pytest.mark.parametrize(
    "conclusion",
    [
        "consensus",
        "partial_consensus",
        "no_consensus",
        "insufficient_evidence",
    ],
)
def test_finalize_accepts_valid_conclusions(
    engine,
    debate,
    conclusion,
):
    result = engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion=conclusion,
        conclusion_text="Final analysis.",
    )

    assert result.status == DebateStatus.COMPLETED.value
    assert result.conclusion == conclusion
    assert result.completed_at is not None


def test_finalize_stores_unresolved_issues(
    engine,
    debate,
):
    result = engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="partial_consensus",
        conclusion_text="Some issues remain unresolved.",
        unresolved_issues=[
            "Revenue forecast requires verification.",
            "Gross margin assumptions need more data.",
        ],
    )

    assert len(result.unresolved_issues) == 2


def test_finalize_deduplicates_unresolved_issues(
    engine,
    debate,
):
    result = engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="partial_consensus",
        conclusion_text="Partial consensus.",
        unresolved_issues=[
            "Revenue forecast",
            "Revenue forecast",
        ],
    )

    assert result.unresolved_issues == [
        "Revenue forecast"
    ]


def test_finalize_completes_open_round(
    engine,
    debate,
):
    result = engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="no_consensus",
        conclusion_text="Agents maintain different views.",
    )

    assert (
        result.rounds[0].status
        == DebateRoundStatus.COMPLETED.value
    )


def test_finalize_rejects_invalid_conclusion(
    engine,
    debate,
):
    with pytest.raises(DebateResponseError):
        engine.finalize_debate(
            debate_id=debate.debate_id,
            conclusion="buy",
            conclusion_text="Invalid conclusion.",
        )


def test_finalize_rejects_empty_conclusion_text(
    engine,
    debate,
):
    with pytest.raises(ValueError):
        engine.finalize_debate(
            debate_id=debate.debate_id,
            conclusion="consensus",
            conclusion_text=" ",
        )


def test_finalize_rejects_second_finalization(
    engine,
    debate,
):
    engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="consensus",
        conclusion_text="First finalization.",
    )

    with pytest.raises(DebateStateError):
        engine.finalize_debate(
            debate_id=debate.debate_id,
            conclusion="no_consensus",
            conclusion_text="Second finalization.",
        )


# ============================================================
# Cancel tests
# ============================================================

def test_cancel_debate(
    engine,
    debate,
):
    result = engine.cancel_debate(
        debate_id=debate.debate_id,
        reason="Research scope changed.",
    )

    assert result.status == DebateStatus.CANCELLED.value
    assert result.completed_at is not None
    assert "Research scope changed" in result.conclusion_text


def test_cancel_debate_without_reason(
    engine,
    debate,
):
    result = engine.cancel_debate(
        debate_id=debate.debate_id,
    )

    assert result.status == DebateStatus.CANCELLED.value


def test_cancel_debate_completes_open_round(
    engine,
    debate,
):
    result = engine.cancel_debate(
        debate_id=debate.debate_id,
    )

    assert (
        result.rounds[0].status
        == DebateRoundStatus.COMPLETED.value
    )


def test_cancel_rejects_completed_debate(
    engine,
    debate,
):
    engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="consensus",
        conclusion_text="Completed.",
    )

    with pytest.raises(DebateStateError):
        engine.cancel_debate(debate.debate_id)


# ============================================================
# Get and list tests
# ============================================================

def test_get_debate_returns_session(
    engine,
    debate,
):
    loaded = engine.get_debate(debate.debate_id)

    assert loaded.debate_id == debate.debate_id
    assert loaded.task_id == "task_001"


def test_get_debate_rejects_missing_id(engine):
    with pytest.raises(DebateNotFoundError):
        engine.get_debate("debate_missing")


def test_list_debates_returns_summaries(
    engine,
    debate,
):
    summaries = engine.list_debates()

    assert len(summaries) == 1
    assert summaries[0].debate_id == debate.debate_id
    assert summaries[0].participant_count == 3
    assert summaries[0].round_count == 1


def test_list_debates_filters_by_task(
    engine,
    debate,
):
    summaries = engine.list_debates(
        task_id="task_002",
    )

    assert summaries == []


def test_list_debates_filters_by_status(
    engine,
    debate,
):
    summaries = engine.list_debates(
        status="in_progress",
    )

    assert len(summaries) == 1

    completed = engine.list_debates(
        status="completed",
    )

    assert completed == []


def test_list_debates_rejects_invalid_status(
    engine,
):
    with pytest.raises(ValueError):
        engine.list_debates(status="unknown")


def test_list_debates_counts_messages(
    engine,
    debate,
):
    submit_all_participants(engine, debate)

    summaries = engine.list_debates()

    assert summaries[0].message_count == 3


# ============================================================
# Persistence tests
# ============================================================

def test_start_debate_creates_json_file(
    engine,
    debate,
):
    path = (
        engine.storage_dir
        / f"debate_{debate.debate_id.split('debate_', 1)[-1]}.json"
    )

    assert path.exists()


def test_save_debate_returns_path(
    engine,
    debate,
):
    path = engine.save_debate(debate)

    assert isinstance(path, Path)
    assert path.exists()


def test_saved_json_is_valid(
    engine,
    debate,
):
    path = engine.save_debate(debate)

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    assert data["debate_id"] == debate.debate_id
    assert data["task_id"] == "task_001"
    assert data["status"] == "in_progress"


def test_debate_can_be_loaded_by_new_engine(
    task_manager,
    cross_validator,
    tmp_path,
):
    storage_dir = tmp_path / "debates"

    first_engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    first_session = first_engine.start_debate(
        task_id="task_001",
    )

    first_engine.submit_response(
        debate_id=first_session.debate_id,
        agent_id="chatgpt",
        content="Persisted response.",
    )

    second_engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    loaded = second_engine.get_debate(
        first_session.debate_id
    )

    assert loaded.debate_id == first_session.debate_id
    assert len(loaded.rounds[0].messages) == 1
    assert (
        loaded.rounds[0].messages[0].content
        == "Persisted response."
    )


def test_new_engine_can_list_persisted_debates(
    task_manager,
    cross_validator,
    tmp_path,
):
    storage_dir = tmp_path / "debates"

    first_engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    first_session = first_engine.start_debate(
        task_id="task_001",
    )

    second_engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    summaries = second_engine.list_debates()

    assert len(summaries) == 1
    assert summaries[0].debate_id == first_session.debate_id


def test_persistence_preserves_final_conclusion(
    task_manager,
    cross_validator,
    tmp_path,
):
    storage_dir = tmp_path / "debates"

    first_engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    session = first_engine.start_debate(
        task_id="task_001",
    )

    first_engine.finalize_debate(
        debate_id=session.debate_id,
        conclusion="partial_consensus",
        conclusion_text="The team reached partial consensus.",
        unresolved_issues=["Revenue forecast"],
    )

    second_engine = DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        storage_dir=storage_dir,
    )

    loaded = second_engine.get_debate(session.debate_id)

    assert loaded.conclusion == "partial_consensus"
    assert loaded.conclusion_text == (
        "The team reached partial consensus."
    )
    assert loaded.unresolved_issues == ["Revenue forecast"]


# ============================================================
# Export tests
# ============================================================

def test_export_debate_returns_dictionary(
    engine,
    debate,
):
    exported = engine.export_debate(debate.debate_id)

    assert isinstance(exported, dict)
    assert exported["debate_id"] == debate.debate_id
    assert exported["task_id"] == "task_001"


def test_export_debate_contains_validation_payload(
    engine,
    debate,
):
    exported = engine.export_debate(debate.debate_id)

    assert "validation_payload" in exported
    assert "conflicts" in exported["validation_payload"]
    assert "consensus" in exported["validation_payload"]


def test_export_debate_markdown_contains_header(
    engine,
    debate,
):
    markdown = engine.export_debate_markdown(
        debate.debate_id
    )

    assert "# AI Team Debate Report" in markdown
    assert debate.debate_id in markdown
    assert "## Final conclusion" in markdown


def test_export_debate_markdown_contains_messages(
    engine,
    debate,
):
    engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        position="support",
        content="The company has strong order visibility.",
        evidence=["Company annual report"],
    )

    markdown = engine.export_debate_markdown(
        debate.debate_id
    )

    assert "The company has strong order visibility." in markdown
    assert "Company annual report" in markdown
    assert "#### chatgpt" in markdown


def test_export_markdown_shows_unresolved_issues(
    engine,
    debate,
):
    engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="partial_consensus",
        conclusion_text="Partial agreement.",
        unresolved_issues=["Need to verify capital expenditure."],
    )

    markdown = engine.export_debate_markdown(
        debate.debate_id
    )

    assert "Need to verify capital expenditure." in markdown


# ============================================================
# Data model tests
# ============================================================

def test_debate_message_to_dict():
    message = DebateMessage(
        message_id="message_001",
        debate_id="debate_001",
        round_number=1,
        agent_id="chatgpt",
        position="support",
        content="Test response.",
        evidence=["Source A"],
    )

    data = message.to_dict()

    assert data["message_id"] == "message_001"
    assert data["position"] == "support"
    assert data["evidence"] == ["Source A"]


def test_debate_round_to_dict():
    debate_round = DebateRound(
        round_number=1,
        prompt="Test prompt.",
    )

    data = debate_round.to_dict()

    assert data["round_number"] == 1
    assert data["status"] == "open"
    assert data["prompt"] == "Test prompt."
    assert data["messages"] == []


def test_debate_session_to_dict(debate):
    data = debate.to_dict()

    assert data["debate_id"] == debate.debate_id
    assert data["task_id"] == "task_001"
    assert data["participants"] == [
        "chatgpt",
        "grok",
        "hark",
    ]
    assert isinstance(data["rounds"], list)


# ============================================================
# Boundary and regression tests
# ============================================================

def test_task_id_validation_rejects_path_traversal(engine):
    with pytest.raises(ValueError):
        engine.start_debate(
            task_id="../outside",
        )


def test_debate_id_validation_rejects_path_traversal(engine):
    with pytest.raises(ValueError):
        engine.get_debate("../outside")


def test_response_content_length_limit(
    engine,
    debate,
):
    with pytest.raises(ValueError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="x" * 50001,
        )


def test_response_evidence_length_limit(
    engine,
    debate,
):
    with pytest.raises(ValueError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="Response.",
            evidence=["x" * 5001],
        )


def test_invalid_round_number_type(
    engine,
    debate,
):
    with pytest.raises(DebateResponseError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="Response.",
            round_number="1",
        )


def test_cancelled_debate_rejects_response(
    engine,
    debate,
):
    engine.cancel_debate(debate.debate_id)

    with pytest.raises(DebateStateError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="Too late.",
        )


def test_completed_debate_rejects_response(
    engine,
    debate,
):
    engine.finalize_debate(
        debate_id=debate.debate_id,
        conclusion="consensus",
        conclusion_text="Finalized.",
    )

    with pytest.raises(DebateStateError):
        engine.submit_response(
            debate_id=debate.debate_id,
            agent_id="chatgpt",
            content="Too late.",
        )


def test_empty_validation_conflicts_are_supported(
    engine,
    validation_payload,
):
    payload = dict(validation_payload)
    payload["conflicts"] = []
    payload["consensus"] = []

    session = engine.start_debate(
        task_id="task_001",
        validation_result=payload,
        force=True,
    )

    assert "No explicit conflicts" in session.rounds[0].prompt
    assert "No consensus items" in session.rounds[0].prompt


def test_invalid_validation_payload_conflicts_type(
    engine,
):
    payload = {
        "task_id": "task_001",
        "conflicts": "not-a-list",
        "consensus": [],
        "agent_analyses": [
            {"agent_id": "chatgpt"},
            {"agent_id": "grok"},
        ],
        "requires_debate": True,
    }

    with pytest.raises(DebateEngineError):
        engine.start_debate(
            task_id="task_001",
            validation_result=payload,
        )


def test_invalid_validation_payload_analyses_type(
    engine,
):
    payload = {
        "task_id": "task_001",
        "conflicts": [],
        "consensus": [],
        "agent_analyses": "not-a-list",
        "requires_debate": True,
    }

    with pytest.raises(DebateEngineError):
        engine.start_debate(
            task_id="task_001",
            validation_result=payload,
        )


def test_missing_agent_analyses_uses_default_agents(
    engine,
):
    payload = {
        "task_id": "task_001",
        "conflicts": [],
        "consensus": [],
        "agent_analyses": [],
        "requires_debate": True,
    }

    session = engine.start_debate(
        task_id="task_001",
        validation_result=payload,
    )

    assert session.participants == [
        "chatgpt",
        "grok",
        "hark",
    ]


def test_json_serialization_preserves_chinese(
    engine,
    debate,
):
    engine.submit_response(
        debate_id=debate.debate_id,
        agent_id="chatgpt",
        content="公司现金流改善，但仍需关注资本开支。",
    )

    path = engine.save_debate(debate)

    raw_text = path.read_text(encoding="utf-8")

    assert "公司现金流改善" in raw_text
    assert "\\u516c\\u53f8" not in raw_text


def test_round_prompt_does_not_invent_market_data(debate):
    prompt = debate.rounds[0].prompt

    assert "Do not fabricate data" in prompt


def test_debate_engine_has_no_trade_execution_api():
    public_methods = {
        name
        for name in dir(DebateEngine)
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
