
"""
AI Hedge Fund OS V3.10
Multi-AI Collaboration Engine

Step 3: Report Collector Tests

Python >= 3.11
Standard library + pytest for testing.
"""

import json

from pathlib import Path

import pytest

from ai_team.task_manager import (
    TaskManager,
    TaskType,
    TaskPriority,
    TaskStatus,
    TaskNotFoundError,
)

from ai_team.report_collector import (
    ReportCollector,
    ReportFormat,
    ReportQuality,
    ReportRecord,
    ReportNotFoundError,
    ReportPersistenceError,
    ReportTaskStateError,
    InvalidReportError,
    DuplicateReportError,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def task_manager(tmp_path: Path):
    """Create an isolated TaskManager."""

    return TaskManager(
        storage_dir=tmp_path / "tasks"
    )


@pytest.fixture
def research_task(task_manager):
    """Create and assign a research task."""

    task = task_manager.create_task(
        title="天孚通信深度研究",
        description=(
            "分析天孚通信的基本面、"
            "光模块产业链和估值水平。"
        ),
        task_type=TaskType.STOCK_RESEARCH,
        target="天孚通信 300394",
        priority=TaskPriority.HIGH,
        requirements=[
            "分析核心业务",
            "分析行业竞争",
            "分析财务表现",
        ],
        expected_outputs=[
            "基本面研究报告",
            "行业研究报告",
            "风险评估",
            "投资结论",
        ],
    )

    task_manager.assign_task(
        task.task_id
    )

    task_manager.start_task(
        task.task_id
    )

    return task


@pytest.fixture
def collector(
    task_manager,
    tmp_path: Path,
):
    """Create an isolated ReportCollector."""

    return ReportCollector(
        task_manager=task_manager,
        storage_dir=tmp_path / "reports",
    )


@pytest.fixture
def complete_report():
    """Return a structurally complete report."""

    return """
# Executive Summary

This report analyzes the company and its business outlook.

# Key Findings

The company operates in the optical communications industry.

# Evidence and Sources

Sources include company filings and industry research.

# Analytical Reasoning

The business model and competitive advantages require evaluation.

# Risks and Limitations

Industry competition and valuation remain important risks.

# Independent Conclusion

The company deserves further research.

# Confidence Level

Medium confidence based on available information.
""".strip()


@pytest.fixture
def incomplete_report():
    return """
# Executive Summary

This is a preliminary research report.

# Key Findings

Several findings require further verification.
""".strip()


def submit_three_reports(
    collector,
    research_task,
    complete_report,
):
    """Submit reports from all three agents."""

    records = []

    for agent_id in (
        "chatgpt",
        "grok",
        "hark",
    ):
        record = collector.collect_report(
            task_id=research_task.task_id,
            agent_id=agent_id,
            content=complete_report,
        )

        records.append(record)

    return records


# ============================================================
# Initialization tests
# ============================================================

def test_collector_initialization(
    task_manager,
    tmp_path,
):
    collector = ReportCollector(
        task_manager=task_manager,
        storage_dir=tmp_path / "reports",
    )

    assert collector.storage_dir.exists()


def test_collector_requires_task_manager(tmp_path):
    with pytest.raises(ValueError):
        ReportCollector(
            task_manager=None,
            storage_dir=tmp_path / "reports",
        )


def test_required_sections_validation(
    task_manager,
    tmp_path,
):
    with pytest.raises(ValueError):
        ReportCollector(
            task_manager=task_manager,
            storage_dir=tmp_path / "reports",
            required_sections=(),
        )


# ============================================================
# Report validation tests
# ============================================================

def test_validate_complete_report(
    collector,
    complete_report,
):
    result = collector.validate_report(
        complete_report
    )

    assert result.is_valid is True

    assert (
        result.quality
        == ReportQuality.COMPLETE.value
    )

    assert result.missing_sections == []

    assert len(result.found_sections) == 7


def test_validate_incomplete_report(
    collector,
    incomplete_report,
):
    result = collector.validate_report(
        incomplete_report
    )

    assert result.is_valid is True

    assert (
        result.quality
        == ReportQuality.INCOMPLETE.value
    )

    assert len(result.missing_sections) > 0


def test_validate_empty_report(collector):
    result = collector.validate_report("")

    assert result.is_valid is False

    assert (
        result.quality
        == ReportQuality.EMPTY.value
    )


def test_validate_non_string_report(collector):
    from ai_team.report_collector import InvalidReportError

    with pytest.raises(InvalidReportError):
        collector.validate_report(None)


def test_validate_markdown_headings(
    collector,
    complete_report,
):
    result = collector.validate_report(
        complete_report
    )

    assert (
        "Executive Summary"
        in result.found_sections
    )

    assert (
        "Confidence Level"
        in result.found_sections
    )


def test_validate_word_count(
    collector,
    complete_report,
):
    result = collector.validate_report(
        complete_report
    )

    assert result.total_characters > 0
    assert result.total_words > 0


# ============================================================
# Report collection tests
# ============================================================

def test_collect_chatgpt_report(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    assert isinstance(record, ReportRecord)

    assert record.agent_id == "chatgpt"

    assert (
        record.quality
        == ReportQuality.COMPLETE.value
    )

    assert Path(record.report_path).exists()

    assert Path(record.metadata_path).exists()


def test_collect_grok_report(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="grok",
        content=complete_report,
    )

    assert record.agent_id == "grok"


def test_collect_hark_report(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="hark",
        content=complete_report,
    )

    assert record.agent_id == "hark"


def test_collect_all_three_reports(
    collector,
    research_task,
    complete_report,
    task_manager,
):
    records = submit_three_reports(
        collector,
        research_task,
        complete_report,
    )

    assert len(records) == 3

    task = task_manager.get_task(
        research_task.task_id
    )

    assert (
        task.status
        == TaskStatus.SUBMITTED.value
    )


def test_collect_report_with_custom_title(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
        title="天孚通信投资研究报告",
    )

    assert record.title == "天孚通信投资研究报告"


def test_collect_report_with_notes(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="grok",
        content=complete_report,
        notes="包含市场舆情分析。",
    )

    assert record.notes == "包含市场舆情分析。"


def test_collect_report_source(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="hark",
        content=complete_report,
        source="manual",
    )

    assert record.source == "manual"


def test_collect_text_format(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
        report_format=ReportFormat.TEXT,
    )

    assert record.format == ReportFormat.TEXT.value


# ============================================================
# Duplicate protection tests
# ============================================================

def test_duplicate_report_rejected(
    collector,
    research_task,
    complete_report,
):
    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    with pytest.raises(DuplicateReportError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=complete_report,
        )


def test_duplicate_submission_across_instances(
    task_manager,
    research_task,
    complete_report,
    tmp_path,
):
    reports_dir = tmp_path / "reports"

    collector_one = ReportCollector(
        task_manager=task_manager,
        storage_dir=reports_dir,
    )

    collector_two = ReportCollector(
        task_manager=task_manager,
        storage_dir=reports_dir,
    )

    collector_one.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    with pytest.raises(DuplicateReportError):
        collector_two.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=complete_report,
        )


# ============================================================
# Task and agent validation tests
# ============================================================

def test_unknown_task_rejected(
    collector,
    complete_report,
):
    with pytest.raises(TaskNotFoundError):
        collector.collect_report(
            task_id="UNKNOWN_TASK",
            agent_id="chatgpt",
            content=complete_report,
        )


def test_unassigned_agent_rejected(
    collector,
    task_manager,
    complete_report,
):
    task = task_manager.create_task(
        title="测试任务",
        description="测试未分配 Agent。",
        task_type=TaskType.GENERAL_RESEARCH,
    )

    task_manager.assign_task(
        task.task_id,
        ["chatgpt"],
    )

    task_manager.start_task(
        task.task_id
    )

    with pytest.raises(InvalidReportError):
        collector.collect_report(
            task_id=task.task_id,
            agent_id="grok",
            content=complete_report,
        )


def test_invalid_agent_rejected(
    collector,
    research_task,
    complete_report,
):
    with pytest.raises(InvalidReportError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="unknown_agent",
            content=complete_report,
        )


def test_task_must_be_in_progress(
    task_manager,
    tmp_path,
    complete_report,
):
    task = task_manager.create_task(
        title="待执行研究任务",
        description="测试任务状态。",
        task_type=TaskType.STOCK_RESEARCH,
    )

    task_manager.assign_task(
        task.task_id
    )

    collector = ReportCollector(
        task_manager=task_manager,
        storage_dir=tmp_path / "reports",
    )

    with pytest.raises(ReportTaskStateError):
        collector.collect_report(
            task_id=task.task_id,
            agent_id="chatgpt",
            content=complete_report,
        )


def test_empty_content_rejected(
    collector,
    research_task,
):
    with pytest.raises(InvalidReportError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content="   ",
        )


# ============================================================
# Strict validation tests
# ============================================================

def test_strict_validation_rejects_incomplete_report(
    task_manager,
    research_task,
    incomplete_report,
    tmp_path,
):
    collector = ReportCollector(
        task_manager=task_manager,
        storage_dir=tmp_path / "strict_reports",
        strict_validation=True,
    )

    with pytest.raises(InvalidReportError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=incomplete_report,
        )


def test_allow_incomplete_false(
    collector,
    research_task,
    incomplete_report,
):
    with pytest.raises(InvalidReportError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=incomplete_report,
            allow_incomplete=False,
        )


def test_incomplete_report_allowed_by_default(
    collector,
    research_task,
    incomplete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=incomplete_report,
    )

    assert (
        record.quality
        == ReportQuality.INCOMPLETE.value
    )


# ============================================================
# File persistence tests
# ============================================================

def test_report_content_saved(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    saved_content = Path(
        record.report_path
    ).read_text(encoding="utf-8")

    assert saved_content == complete_report


def test_metadata_saved_as_json(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="grok",
        content=complete_report,
    )

    metadata = json.loads(
        Path(record.metadata_path).read_text(
            encoding="utf-8"
        )
    )

    assert metadata["task_id"] == research_task.task_id
    assert metadata["agent_id"] == "grok"
    assert metadata["report_id"] == record.report_id


def test_metadata_can_be_reloaded(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="hark",
        content=complete_report,
    )

    loaded = collector.get_report(
        record.report_id
    )

    assert loaded.report_id == record.report_id
    assert loaded.agent_id == "hark"


def test_report_can_be_read(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    content = collector.read_report(
        record.report_id
    )

    assert content == complete_report


def test_report_not_found(collector):
    with pytest.raises(ReportNotFoundError):
        collector.get_report("UNKNOWN_REPORT")


def test_missing_report_file(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    Path(record.report_path).unlink()

    with pytest.raises(ReportNotFoundError):
        collector.read_report(record.report_id)


# ============================================================
# Report listing tests
# ============================================================

def test_list_all_reports(
    collector,
    research_task,
    complete_report,
):
    submit_three_reports(
        collector,
        research_task,
        complete_report,
    )

    reports = collector.list_reports()

    assert len(reports) == 3


def test_list_reports_by_task(
    collector,
    research_task,
    complete_report,
):
    submit_three_reports(
        collector,
        research_task,
        complete_report,
    )

    reports = collector.list_reports(
        task_id=research_task.task_id
    )

    assert len(reports) == 3


def test_list_reports_by_agent(
    collector,
    research_task,
    complete_report,
):
    submit_three_reports(
        collector,
        research_task,
        complete_report,
    )

    reports = collector.list_reports(
        agent_id="grok"
    )

    assert len(reports) == 1
    assert reports[0].agent_id == "grok"


def test_list_reports_by_quality(
    collector,
    research_task,
    complete_report,
    incomplete_report,
):
    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="grok",
        content=incomplete_report,
    )

    reports = collector.list_reports(
        quality=ReportQuality.COMPLETE
    )

    assert len(reports) == 1
    assert reports[0].agent_id == "chatgpt"


# ============================================================
# Collection summary tests
# ============================================================

def test_collection_summary_partial(
    collector,
    research_task,
    complete_report,
):
    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    summary = collector.get_collection_summary(
        research_task.task_id
    )

    assert summary["total_assigned"] == 3
    assert summary["total_submitted"] == 1
    assert summary["total_missing"] == 2

    assert summary["completion_ratio"] == pytest.approx(
        1 / 3
    )


def test_collection_summary_complete(
    collector,
    research_task,
    complete_report,
):
    submit_three_reports(
        collector,
        research_task,
        complete_report,
    )

    summary = collector.get_collection_summary(
        research_task.task_id
    )

    assert summary["total_assigned"] == 3
    assert summary["total_submitted"] == 3
    assert summary["total_missing"] == 0

    assert summary["completion_ratio"] == 1.0


def test_collection_summary_missing_agents(
    collector,
    research_task,
    complete_report,
):
    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    summary = collector.get_collection_summary(
        research_task.task_id
    )

    assert summary["missing_agents"] == [
        "grok",
        "hark",
    ]


def test_collection_summary_incomplete_count(
    collector,
    research_task,
    complete_report,
    incomplete_report,
):
    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="grok",
        content=incomplete_report,
    )

    summary = collector.get_collection_summary(
        research_task.task_id
    )

    assert summary["complete_reports"] == 1
    assert summary["incomplete_reports"] == 1


# ============================================================
# Task synchronization tests
# ============================================================

def test_task_manager_submission_sync(
    collector,
    research_task,
    complete_report,
    task_manager,
):
    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    task = task_manager.get_task(
        research_task.task_id
    )

    assert (
        task.assignments["chatgpt"].status
        == "submitted"
    )

    assert task.assignments["chatgpt"].report_path is not None


def test_task_manager_rejects_duplicate_submission(
    collector,
    research_task,
    complete_report,
    task_manager,
):
    collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    with pytest.raises(DuplicateReportError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=complete_report,
        )

    task = task_manager.get_task(
        research_task.task_id
    )

    assert (
        task.assignments["chatgpt"].status
        == "submitted"
    )


# ============================================================
# Input validation tests
# ============================================================

def test_invalid_report_format(
    collector,
    research_task,
    complete_report,
):
    with pytest.raises(ValueError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=complete_report,
            report_format="pdf",
        )


def test_invalid_task_id_format(
    collector,
    complete_report,
):
    with pytest.raises(ValueError):
        collector.collect_report(
            task_id="../outside",
            agent_id="chatgpt",
            content=complete_report,
        )


def test_invalid_agent_id_format(
    collector,
    research_task,
    complete_report,
):
    with pytest.raises(ValueError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="../grok",
            content=complete_report,
        )


def test_empty_title_rejected(
    collector,
    research_task,
    complete_report,
):
    with pytest.raises(ValueError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=complete_report,
            title=" ",
        )


def test_invalid_allow_incomplete_type(
    collector,
    research_task,
    complete_report,
):
    with pytest.raises(ValueError):
        collector.collect_report(
            task_id=research_task.task_id,
            agent_id="chatgpt",
            content=complete_report,
            allow_incomplete="yes",
        )


def test_report_format_defaults_to_markdown(
    collector,
    research_task,
    complete_report,
):
    record = collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    assert record.format == "markdown"


# ============================================================
# Persistence and restart tests
# ============================================================

def test_collector_restart_loads_reports(
    task_manager,
    research_task,
    complete_report,
    tmp_path,
):
    reports_dir = tmp_path / "reports"

    collector_one = ReportCollector(
        task_manager=task_manager,
        storage_dir=reports_dir,
    )

    record = collector_one.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    collector_two = ReportCollector(
        task_manager=task_manager,
        storage_dir=reports_dir,
    )

    loaded = collector_two.get_report(
        record.report_id
    )

    assert loaded.report_id == record.report_id


def test_reports_are_separated_by_task(
    task_manager,
    tmp_path,
    complete_report,
):
    task_one = task_manager.create_task(
        title="研究任务一",
        description="第一项研究。",
        task_type=TaskType.STOCK_RESEARCH,
    )

    task_two = task_manager.create_task(
        title="研究任务二",
        description="第二项研究。",
        task_type=TaskType.GENERAL_RESEARCH,
    )

    for task in (task_one, task_two):
        task_manager.assign_task(task.task_id)
        task_manager.start_task(task.task_id)

    collector = ReportCollector(
        task_manager=task_manager,
        storage_dir=tmp_path / "reports",
    )

    record_one = collector.collect_report(
        task_id=task_one.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    record_two = collector.collect_report(
        task_id=task_two.task_id,
        agent_id="chatgpt",
        content=complete_report,
    )

    assert record_one.task_id != record_two.task_id
    assert Path(record_one.report_path).parent != Path(
        record_two.report_path
    )


# ============================================================
# Final integration test
# ============================================================

def test_full_three_ai_report_collection_workflow(
    task_manager,
    tmp_path,
    complete_report,
):
    """
    Complete workflow:

    1. Create research task.
    2. Assign ChatGPT, Grok and Hark.
    3. Start task.
    4. Collect three independent reports.
    5. Verify persisted files.
    6. Verify task synchronization.
    7. Verify collection summary.
    """

    task = task_manager.create_task(
        title="AI三智能体协作研究",
        description="测试三个 AI 的报告收集流程。",
        task_type=TaskType.STOCK_RESEARCH,
        target="天孚通信 300394",
    )

    task_manager.assign_task(
        task.task_id
    )

    task_manager.start_task(
        task.task_id
    )

    collector = ReportCollector(
        task_manager=task_manager,
        storage_dir=tmp_path / "reports",
    )

    records = []

    for agent_id in (
        "chatgpt",
        "grok",
        "hark",
    ):
        records.append(
            collector.collect_report(
                task_id=task.task_id,
                agent_id=agent_id,
                content=complete_report,
            )
        )

    assert len(records) == 3

    for record in records:
        assert Path(record.report_path).exists()
        assert Path(record.metadata_path).exists()

    summary = collector.get_collection_summary(
        task.task_id
    )

    assert summary["total_submitted"] == 3
    assert summary["total_missing"] == 0
    assert summary["completion_ratio"] == 1.0

    final_task = task_manager.get_task(
        task.task_id
    )

    assert (
        final_task.status
        == TaskStatus.SUBMITTED.value
    )

    for agent_id in (
        "chatgpt",
        "grok",
        "hark",
    ):
        assert (
            final_task.assignments[agent_id].status
            == "submitted"
        )
