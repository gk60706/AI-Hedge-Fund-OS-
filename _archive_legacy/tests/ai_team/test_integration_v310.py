from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ai_team.config import get_default_config
from ai_team.task_manager import TaskManager
from ai_team.report_collector import ReportCollector
from ai_team.cross_validator import CrossValidator
from ai_team.debate_engine import (
    DebateConclusion,
    DebateEngine,
    DebatePosition,
)
from ai_team.consensus_engine import ConsensusEngine
from ai_team.investment_committee import InvestmentCommittee


# =========================================================
# Test constants
# =========================================================

TEST_SYMBOL = "300394"

TEST_REPORTS = {
    "chatgpt": {
        "title": "CIO independent research report",
        "content": """
# Executive Summary

The company operates in the optical communication industry.
The investment thesis requires confirmation from order growth,
gross margin trends, and customer demand.

# Key Findings

The optical communication industry may benefit from data center
investment. Actual company-level growth still requires verification.

# Evidence and Sources

- Evidence: illustrative industry demand observation.
- Evidence: company financial information should be checked
  against official disclosures.

# Analytical Reasoning

Industry growth does not automatically translate into company
earnings growth. Production capacity, product mix, customer
concentration, and delivery capability must also be evaluated.

# Risks and Limitations

- Industry demand may slow.
- Valuation may already reflect optimistic expectations.
- The available test data is illustrative, not live market data.

# Independent Conclusion

Maintain a watch position until more financial and order evidence
becomes available.

# Confidence Level

0.72
""".strip(),
    },
    "grok": {
        "title": "Market intelligence research report",
        "content": """
# Executive Summary

The industry outlook is potentially constructive, but short-term
price action and capital flows should not be confused with
fundamental improvement.

# Key Findings

Industry demand, customer capital expenditure, and supply-chain
capacity are important variables for the company's outlook.

# Evidence and Sources

- Evidence: illustrative industry investment trend.
- Evidence: public company disclosures should be reviewed
  before forming a final investment opinion.

# Analytical Reasoning

A favorable industry narrative needs confirmation from actual
orders, shipment growth, and profitability. Market sentiment
alone is insufficient.

# Risks and Limitations

- Market expectations may be excessive.
- Capital expenditure cycles can change.
- The supplied test information does not contain real-time quotes.

# Independent Conclusion

The company is worth continued monitoring, but the current
evidence does not justify an unconditional buy recommendation.

# Confidence Level

0.76
""".strip(),
    },
    "hark": {
        "title": "Independent analyst research report",
        "content": """
# Executive Summary

The company should be evaluated through business quality,
financial performance, valuation, and industry competition.

# Key Findings

The optical communication supply chain has meaningful growth
opportunities, but individual company performance depends on
product competitiveness and customer relationships.

# Evidence and Sources

- Evidence: illustrative company research assumptions.
- Evidence: official financial reports are required for
  verification.

# Analytical Reasoning

The investment case should be supported by revenue growth,
profitability, cash flow, and reasonable valuation. A single
industry growth indicator is not enough.

# Risks and Limitations

- Customer concentration.
- Technology iteration.
- Capacity expansion and execution risk.
- Valuation uncertainty.

# Independent Conclusion

Continue research and monitor financial disclosures before
making a stronger investment decision.

# Confidence Level

0.80
""".strip(),
    },
}


# =========================================================
# Fixtures
# =========================================================

@pytest.fixture
def project_config(tmp_path: Path):
    """Create a fully isolated project configuration."""

    config = get_default_config(project_root=tmp_path)
    config.create_directories()

    assert config.project_root == tmp_path.resolve()
    assert config.team_dir.is_dir()
    assert config.tasks_dir.is_dir()
    assert config.reports_dir.is_dir()
    assert config.evaluation_dir.is_dir()

    return config


@pytest.fixture
def task_manager(project_config):
    return TaskManager(
        config=project_config,
        storage_dir=project_config.tasks_dir,
    )


@pytest.fixture
def report_collector(task_manager, project_config):
    return ReportCollector(
        task_manager=task_manager,
        storage_dir=project_config.reports_dir,
        strict_validation=False,
    )


@pytest.fixture
def cross_validator(
    task_manager,
    report_collector,
    project_config,
):
    return CrossValidator(
        task_manager=task_manager,
        report_collector=report_collector,
        storage_dir=project_config.evaluation_dir,
        min_reports=2,
    )


@pytest.fixture
def debate_engine(
    task_manager,
    cross_validator,
    report_collector,
    project_config,
):
    return DebateEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        report_collector=report_collector,
        storage_dir=project_config.evaluation_dir / "debates",
        default_max_rounds=1,
    )


@pytest.fixture
def consensus_engine(
    task_manager,
    cross_validator,
    debate_engine,
    project_config,
):
    return ConsensusEngine(
        task_manager=task_manager,
        cross_validator=cross_validator,
        debate_engine=debate_engine,
        storage_dir=project_config.evaluation_dir / "consensus",
    )


@pytest.fixture
def investment_committee(
    task_manager,
    consensus_engine,
    project_config,
):
    return InvestmentCommittee(
        task_manager=task_manager,
        consensus_engine=consensus_engine,
        storage_dir=project_config.evaluation_dir / "committee",
    )


# =========================================================
# Helpers
# =========================================================

def _object_value(obj: Any, name: str, default=None):
    """Read a value from either a dataclass or dictionary."""

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def _identifier(obj: Any, *names: str) -> str:
    """Read the first available non-empty identifier."""

    for name in names:
        value = _object_value(obj, name)

        if value:
            return str(value)

    raise AssertionError(
        f"Object {type(obj).__name__} has no identifier in {names}"
    )


def _create_started_task(task_manager: TaskManager) -> str:
    """Create, assign, and start a three-agent stock research task."""

    task = task_manager.create_task(
        title="V3.10 integration research: 300394",
        description=(
            "Run an isolated end-to-end AI team research workflow. "
            "Use test-only evidence and do not execute any trade."
        ),
        task_type="stock_research",
        priority="high",
        target=TEST_SYMBOL,
        requirements=[
            "Independent research from three agents",
            "Cross-agent validation",
            "Debate and consensus",
            "Investment committee review",
        ],
        expected_outputs=[
            "Three independent research reports",
            "Cross-validation result",
            "Debate result",
            "Consensus report",
            "Investment committee decision",
        ],
        metadata={
            "integration_test": True,
            "paper_trade_only": True,
        },
        created_by="pytest",
    )

    task_id = _identifier(task, "task_id")

    task_manager.assign_task(
        task_id,
        agent_ids=["chatgpt", "grok", "hark"],
    )

    task_manager.start_task(task_id)

    return task_id


def _collect_three_reports(
    report_collector: ReportCollector,
    task_id: str,
) -> list[Any]:
    """Collect one independent report from each configured agent."""

    records = []

    for agent_id in ("chatgpt", "grok", "hark"):
        report = TEST_REPORTS[agent_id]

        record = report_collector.collect_report(
            task_id=task_id,
            agent_id=agent_id,
            content=report["content"],
            title=report["title"],
            source="integration_test",
            notes="Generated test fixture; not investment advice.",
            allow_incomplete=False,
        )

        records.append(record)

    return records


def _start_and_finalize_debate(
    debate_engine: DebateEngine,
    task_id: str,
    validation_result: Any,
) -> Any:
    """Run a complete one-round debate."""

    session = debate_engine.start_debate(
        task_id=task_id,
        validation_result=validation_result,
        participants=["chatgpt", "grok", "hark"],
        max_rounds=1,
        force=True,
    )

    debate_id = _identifier(session, "debate_id")

    responses = [
        (
            "chatgpt",
            DebatePosition.NEUTRAL,
            (
                "The industry outlook is constructive, but "
                "valuation and financial evidence need further review."
            ),
        ),
        (
            "grok",
            DebatePosition.SUPPORT,
            (
                "Potential industry demand provides a positive "
                "research direction, subject to order confirmation."
            ),
        ),
        (
            "hark",
            DebatePosition.NEUTRAL,
            (
                "The company deserves continued monitoring, "
                "but available evidence does not support an "
                "unconditional investment conclusion."
            ),
        ),
    ]

    for agent_id, position, content in responses:
        debate_engine.submit_response(
            debate_id=debate_id,
            agent_id=agent_id,
            content=content,
            position=position,
            evidence=[
                "Illustrative test evidence only."
            ],
        )

    debate = debate_engine.finalize_debate(
        debate_id=debate_id,
        conclusion=DebateConclusion.PARTIAL_CONSENSUS,
        conclusion_text=(
            "The agents agree that the company deserves "
            "continued research, while valuation and financial "
            "confirmation remain unresolved."
        ),
        unresolved_issues=[
            "Verify actual order growth.",
            "Review the latest financial statements.",
            "Evaluate current valuation against earnings growth.",
        ],
    )

    return debate


# =========================================================
# Integration: config
# =========================================================

def test_config_uses_tmp_path(project_config, tmp_path: Path):
    assert project_config.project_root == tmp_path.resolve()

    assert project_config.api_enabled is False
    assert project_config.manual_handoff_required is True

    assert project_config.tasks_dir.is_relative_to(tmp_path.resolve())
    assert project_config.reports_dir.is_relative_to(tmp_path.resolve())
    assert project_config.evaluation_dir.is_relative_to(tmp_path.resolve())


# =========================================================
# Integration: task manager
# =========================================================

def test_task_creation_assignment_and_start(task_manager):
    task_id = _create_started_task(task_manager)

    task = task_manager.get_task(task_id)

    assert task is not None
    assert task.task_id == task_id
    assert task.target == TEST_SYMBOL
    assert len(task.assignments) == 3

    assert {
        "chatgpt",
        "grok",
        "hark",
    }.issubset(set(task.assignments.keys()))


# =========================================================
# Integration: report collection
# =========================================================

def test_report_collection_updates_task(
    task_manager,
    report_collector,
):
    task_id = _create_started_task(task_manager)

    records = _collect_three_reports(
        report_collector,
        task_id,
    )

    assert len(records) == 3

    report_ids = {
        _identifier(record, "report_id")
        for record in records
    }

    assert len(report_ids) == 3

    stored_reports = report_collector.list_reports(
        task_id=task_id,
    )

    assert len(stored_reports) == 3

    task = task_manager.get_task(task_id)

    assert task is not None

    for agent_id in ("chatgpt", "grok", "hark"):
        assert agent_id in task.assignments


# =========================================================
# Integration: cross validation
# =========================================================

def test_cross_validation_consumes_collected_reports(
    task_manager,
    report_collector,
    cross_validator,
):
    task_id = _create_started_task(task_manager)

    _collect_three_reports(
        report_collector,
        task_id,
    )

    result = cross_validator.validate_task(task_id)

    assert result is not None
    assert _object_value(result, "task_id") == task_id
    assert _object_value(result, "report_count") >= 2

    assert _object_value(result, "validation_id")
    assert _object_value(result, "agent_analyses") is not None
    assert _object_value(result, "conflicts") is not None
    assert _object_value(result, "consensus") is not None

    assert 0 <= _object_value(result, "agreement_score") <= 1


# =========================================================
# Integration: debate
# =========================================================

def test_debate_uses_cross_validation_result(
    task_manager,
    report_collector,
    cross_validator,
    debate_engine,
):
    task_id = _create_started_task(task_manager)

    _collect_three_reports(
        report_collector,
        task_id,
    )

    validation_result = cross_validator.validate_task(task_id)

    debate = _start_and_finalize_debate(
        debate_engine=debate_engine,
        task_id=task_id,
        validation_result=validation_result,
    )

    assert debate is not None
    assert _object_value(debate, "task_id") == task_id
    assert _object_value(debate, "debate_id")
    assert _object_value(debate, "status") is not None

    stored = debate_engine.get_debate(
        _identifier(debate, "debate_id")
    )

    assert stored is not None


# =========================================================
# Integration: consensus
# =========================================================

def test_consensus_uses_validation_and_debate(
    task_manager,
    report_collector,
    cross_validator,
    debate_engine,
    consensus_engine,
):
    task_id = _create_started_task(task_manager)

    _collect_three_reports(
        report_collector,
        task_id,
    )

    validation_result = cross_validator.validate_task(task_id)

    debate = _start_and_finalize_debate(
        debate_engine=debate_engine,
        task_id=task_id,
        validation_result=validation_result,
    )

    consensus = consensus_engine.build_consensus(
        task_id=task_id,
        validation_result=validation_result,
        debate=debate,
        participants=["chatgpt", "grok", "hark"],
        force=True,
    )

    assert consensus is not None
    assert _object_value(consensus, "task_id") == task_id
    assert _object_value(consensus, "consensus_id")

    assert _object_value(consensus, "validation_id")
    assert _object_value(consensus, "debate_id")

    assert _object_value(consensus, "votes") is not None
    assert _object_value(consensus, "issues") is not None

    # consensus_engine 的 confidence 是文字等级（low/medium/high），
    # 不是 0~1 的数值，这里按等级枚举校验。
    assert _object_value(consensus, "confidence") in {"low", "medium", "high"}
    assert 0 <= _object_value(consensus, "agreement_score") <= 1
    assert 0 <= _object_value(consensus, "evidence_score") <= 1

    stored = consensus_engine.get_report(
        _identifier(consensus, "consensus_id")
    )

    assert stored is not None


# =========================================================
# Integration: investment committee
# =========================================================

def test_investment_committee_uses_consensus(
    task_manager,
    report_collector,
    cross_validator,
    debate_engine,
    consensus_engine,
    investment_committee,
):
    task_id = _create_started_task(task_manager)

    _collect_three_reports(
        report_collector,
        task_id,
    )

    validation_result = cross_validator.validate_task(task_id)

    debate = _start_and_finalize_debate(
        debate_engine=debate_engine,
        task_id=task_id,
        validation_result=validation_result,
    )

    consensus = consensus_engine.build_consensus(
        task_id=task_id,
        validation_result=validation_result,
        debate=debate,
        participants=["chatgpt", "grok", "hark"],
        force=True,
    )

    decision = investment_committee.convene(
        task_id=task_id,
        consensus_report=consensus,
        rationale=(
            "Integration test: evaluate the consensus result "
            "and produce a research-only committee decision."
        ),
        force=True,
    )

    assert decision is not None
    assert _object_value(decision, "task_id") == task_id

    decision_id = _identifier(
        decision,
        "decision_id",
    )

    stored = investment_committee.get_decision(decision_id)

    assert stored is not None

    listed = investment_committee.list_decisions(
        task_id=task_id,
    )

    assert len(listed) >= 1


# =========================================================
# Full end-to-end integration
# =========================================================

def test_full_v310_end_to_end_pipeline(
    project_config,
    task_manager,
    report_collector,
    cross_validator,
    debate_engine,
    consensus_engine,
    investment_committee,
):
    """Run config -> task -> reports -> validation -> debate
    -> consensus -> investment committee.

    Every persistent artifact must remain inside tmp_path.
    """

    root = project_config.project_root

    # 1. Task
    task_id = _create_started_task(task_manager)

    # 2. Independent reports
    report_records = _collect_three_reports(
        report_collector,
        task_id,
    )

    assert len(report_records) == 3

    # 3. Cross validation
    validation_result = cross_validator.validate_task(task_id)

    assert _object_value(validation_result, "task_id") == task_id
    assert _object_value(validation_result, "report_count") >= 2

    # 4. Debate
    debate = _start_and_finalize_debate(
        debate_engine=debate_engine,
        task_id=task_id,
        validation_result=validation_result,
    )

    assert _object_value(debate, "task_id") == task_id

    # 5. Consensus
    consensus = consensus_engine.build_consensus(
        task_id=task_id,
        validation_result=validation_result,
        debate=debate,
        participants=["chatgpt", "grok", "hark"],
        force=True,
    )

    assert _object_value(consensus, "task_id") == task_id

    # 6. Investment committee
    decision = investment_committee.convene(
        task_id=task_id,
        consensus_report=consensus,
        rationale=(
            "End-to-end integration test. "
            "Research and paper-trading evaluation only."
        ),
        force=True,
    )

    decision_id = _identifier(
        decision,
        "decision_id",
    )

    assert investment_committee.get_decision(decision_id) is not None

    # 7. Confirm all expected persistence directories are isolated.
    expected_directories = [
        project_config.tasks_dir,
        project_config.reports_dir,
        project_config.evaluation_dir,
        project_config.evaluation_dir / "debates",
        project_config.evaluation_dir / "consensus",
        project_config.evaluation_dir / "committee",
    ]

    for directory in expected_directories:
        resolved = Path(directory).resolve()

        assert resolved.is_relative_to(root), (
            f"Persistent directory escaped tmp_path: {resolved}"
        )

    # 8. Confirm no broker/live-trading integration is involved.
    assert project_config.api_enabled is False
    assert project_config.manual_handoff_required is True

    task = task_manager.get_task(task_id)

    assert task is not None
    assert task.target == TEST_SYMBOL


# =========================================================
# Persistence and isolation
# =========================================================

def test_two_runs_do_not_share_storage(
    tmp_path: Path,
):
    root_a = tmp_path / "run_a"
    root_b = tmp_path / "run_b"

    config_a = get_default_config(project_root=root_a)
    config_b = get_default_config(project_root=root_b)

    config_a.create_directories()
    config_b.create_directories()

    manager_a = TaskManager(
        config=config_a,
        storage_dir=config_a.tasks_dir,
    )

    manager_b = TaskManager(
        config=config_b,
        storage_dir=config_b.tasks_dir,
    )

    task_a = manager_a.create_task(
        title="Run A task",
        description="Isolation test A.",
        task_type="stock_research",
        target=TEST_SYMBOL,
        created_by="pytest",
    )

    task_b = manager_b.create_task(
        title="Run B task",
        description="Isolation test B.",
        task_type="stock_research",
        target=TEST_SYMBOL,
        created_by="pytest",
    )

    task_id_a = _identifier(task_a, "task_id")
    task_id_b = _identifier(task_b, "task_id")

    assert manager_a.get_task(task_id_a) is not None
    assert manager_b.get_task(task_id_b) is not None

    assert config_a.tasks_dir != config_b.tasks_dir
    assert config_a.reports_dir != config_b.reports_dir

    assert config_a.tasks_dir.is_relative_to(root_a.resolve())
    assert config_b.tasks_dir.is_relative_to(root_b.resolve())


# =========================================================
# Failure behavior
# =========================================================

def test_cross_validation_fails_without_enough_reports(
    task_manager,
    report_collector,
    cross_validator,
):
    task_id = _create_started_task(task_manager)

    # Only one report is collected.
    report = TEST_REPORTS["chatgpt"]

    report_collector.collect_report(
        task_id=task_id,
        agent_id="chatgpt",
        content=report["content"],
        title=report["title"],
        source="integration_test",
        allow_incomplete=False,
    )

    with pytest.raises(Exception):
        cross_validator.validate_task(
            task_id,
            min_reports=2,
        )


def test_unknown_task_does_not_produce_committee_decision(
    investment_committee,
):
    with pytest.raises(Exception):
        investment_committee.convene(
            task_id="non-existent-task",
            rationale="Invalid task integration test.",
        )


# =========================================================
# No live-trading interface
# =========================================================

def test_integration_modules_do_not_expose_live_order_methods(
    task_manager,
    report_collector,
    cross_validator,
    debate_engine,
    consensus_engine,
    investment_committee,
):
    modules = [
        task_manager,
        report_collector,
        cross_validator,
        debate_engine,
        consensus_engine,
        investment_committee,
    ]

    forbidden_methods = {
        "place_order",
        "submit_order",
        "execute_order",
        "execute_trade",
        "connect_broker",
        "send_order",
        "live_trade",
    }

    for module in modules:
        public_methods = {
            name
            for name in dir(module)
            if not name.startswith("_")
        }

        assert forbidden_methods.isdisjoint(public_methods)


if __name__ == "__main__":
    raise SystemExit(
        pytest.main([__file__, "-v"])
    )