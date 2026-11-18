
"""
AI Hedge Fund OS V3.10
Multi-AI Collaboration Engine

Step 4: Cross Validator Tests

File:
tests/ai_team/test_cross_validator.py

Python >= 3.11
Testing dependency: pytest

Run:
python -m pytest tests/ai_team/test_cross_validator.py -v
"""

import json

from pathlib import Path

import pytest

from ai_team.task_manager import (
    TaskManager,
    TaskType,
    TaskPriority,
)

from ai_team.report_collector import (
    ReportCollector,
)

from ai_team.cross_validator import (
    CrossValidator,
    CrossValidationResult,
    ExtractedClaim,
    AgentReportAnalysis,
    ClaimCategory,
    ClaimDirection,
    ConflictSeverity,
    EvidenceLevel,
    ValidationStatus,
    InsufficientReportsError,
    CrossValidationReportError,
    CrossValidationPersistenceError,
    ValidationResultNotFoundError,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def task_manager(tmp_path):

    return TaskManager(
        storage_dir=tmp_path / "tasks"
    )


@pytest.fixture
def research_task(task_manager):

    task = task_manager.create_task(
        title="天孚通信深度研究",
        description=(
            "研究天孚通信的业务、"
            "光通信产业链、财务和估值。"
        ),
        task_type=TaskType.STOCK_RESEARCH,
        priority=TaskPriority.HIGH,
        target="天孚通信 300394",
        requirements=[
            "研究公司基本面",
            "研究产业链供需",
            "研究财务情况",
            "分析投资风险",
        ],
        expected_outputs=[
            "基本面研究报告",
            "产业研究报告",
            "财务研究报告",
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
def report_collector(
    task_manager,
    tmp_path,
):

    return ReportCollector(
        task_manager=task_manager,
        storage_dir=tmp_path / "reports",
    )


@pytest.fixture
def validator(
    task_manager,
    report_collector,
    tmp_path,
):

    return CrossValidator(
        task_manager=task_manager,
        report_collector=report_collector,
        storage_dir=tmp_path / "cross_validation",
    )


# ============================================================
# Sample reports
# ============================================================

@pytest.fixture
def bullish_report():

    return """
# Executive Summary

The company has a strong long-term investment outlook.

# Key Findings

- The optical communications industry growth outlook is strong.
- Revenue growth is positive and demand continues to increase.
- The company has strong competitive advantages.

# Evidence and Sources

According to annual report 2025, revenue increased by 25%.
Official company filing: https://example.com/report
Industry data indicates demand growth of 20%.

# Analytical Reasoning

The industry expansion and rising demand support future growth.

# Risks and Limitations

Industry competition and valuation risks remain.

# Independent Conclusion

The company has a positive investment outlook.

# Confidence Level

High confidence based on available evidence.
""".strip()


@pytest.fixture
def bearish_report():

    return """
# Executive Summary

The company has a cautious investment outlook.

# Key Findings

- The optical communications industry growth outlook is weak.
- Revenue growth is negative and demand continues to decrease.
- The company faces weak competitive advantages.

# Evidence and Sources

According to annual report 2025, revenue declined by 15%.
Official company filing: https://example.com/filing
Industry data indicates demand decline of 10%.

# Analytical Reasoning

Weak demand and rising competition may pressure future growth.

# Risks and Limitations

Industry demand and valuation risks remain.

# Independent Conclusion

The company has a negative investment outlook.

# Confidence Level

Medium confidence based on available evidence.
""".strip()


@pytest.fixture
def neutral_report():

    return """
# Executive Summary

The company requires further research.

# Key Findings

- The optical communications industry growth outlook is uncertain.
- Revenue performance requires further investigation.
- The company operates in a competitive market.

# Evidence and Sources

According to annual report 2025, revenue was 100亿元.
Official filing: https://example.com/financial-report

# Analytical Reasoning

Future performance depends on demand and execution.

# Risks and Limitations

Market volatility remains a major risk.

# Independent Conclusion

The investment outlook remains neutral.

# Confidence Level

Medium confidence.
""".strip()


@pytest.fixture
def common_report():

    return """
# Executive Summary

The company operates in an expanding industry.

# Key Findings

- The optical communications industry has strong growth potential.
- Demand for optical communication products is increasing.
- Industry capacity expansion requires monitoring.

# Evidence and Sources

According to annual report 2025, revenue increased by 25%.
Official report: https://example.com/annual-report

# Analytical Reasoning

The expansion of data center infrastructure supports demand.

# Risks and Limitations

Industry competition remains a risk.

# Independent Conclusion

The optical communications industry has strong growth potential.

# Confidence Level

Medium confidence.
""".strip()


def submit_report(
    collector,
    task_id,
    agent_id,
    content,
):

    return collector.collect_report(
        task_id=task_id,
        agent_id=agent_id,
        content=content,
    )


def submit_three_reports(
    collector,
    task_id,
    bullish,
    bearish,
    neutral,
):

    records = []

    reports = {
        "chatgpt": bullish,
        "grok": bearish,
        "hark": neutral,
    }

    for agent_id, content in reports.items():

        records.append(
            submit_report(
                collector,
                task_id,
                agent_id,
                content,
            )
        )

    return records


# ============================================================
# Initialization tests
# ============================================================

def test_validator_initialization(
    validator,
):

    assert isinstance(
        validator,
        CrossValidator,
    )

    assert validator.storage_dir.exists()


def test_validator_requires_task_manager(
    report_collector,
    tmp_path,
):

    with pytest.raises(ValueError):

        CrossValidator(
            task_manager=None,
            report_collector=report_collector,
            storage_dir=tmp_path,
        )


def test_validator_requires_report_collector(
    task_manager,
    tmp_path,
):

    with pytest.raises(ValueError):

        CrossValidator(
            task_manager=task_manager,
            report_collector=None,
            storage_dir=tmp_path,
        )


def test_min_reports_must_be_at_least_one(
    task_manager, report_collector
):
    with pytest.raises(ValueError, match="min_reports must be at least 1"):
        CrossValidator(task_manager, report_collector, min_reports=0)


def test_invalid_claim_limit(
    task_manager,
    report_collector,
    tmp_path,
):

    with pytest.raises(ValueError):

        CrossValidator(
            task_manager=task_manager,
            report_collector=report_collector,
            storage_dir=tmp_path / "validation",
            max_claims_per_agent=0,
        )


# ============================================================
# Section parsing tests
# ============================================================

def test_parse_markdown_sections(
    validator,
    bullish_report,
):

    sections = validator.parse_sections(
        bullish_report
    )

    assert "key_findings" in sections
    assert "evidence" in sections
    assert "reasoning" in sections
    assert "risks" in sections
    assert "conclusion" in sections


def test_parse_section_content(
    validator,
    bullish_report,
):

    sections = validator.parse_sections(
        bullish_report
    )

    assert "Revenue growth" in sections[
        "key_findings"
    ]


def test_parse_chinese_sections(
    validator,
):

    content = """
# 核心发现

公司收入增长。

# 证据与来源

根据公司2025年年报。

# 风险

市场竞争加剧。

# 投资结论

谨慎看多。
"""

    sections = validator.parse_sections(
        content
    )

    assert "key_findings" in sections
    assert "evidence" in sections
    assert "risks" in sections
    assert "conclusion" in sections


def test_parse_numbered_headings(
    validator,
):

    content = """
## 1. Key Findings

Revenue growth is strong.

## 2. Evidence and Sources

According to annual report 2025.
"""

    sections = validator.parse_sections(
        content
    )

    assert "key_findings" in sections
    assert "evidence" in sections


def test_parse_empty_content(
    validator,
):

    sections = validator.parse_sections("")

    assert sections["preamble"] == ""


def test_parse_rejects_non_string_content(
    validator,
):

    with pytest.raises(
        CrossValidationReportError
    ):

        validator.parse_sections(None)


# ============================================================
# Category classification tests
# ============================================================

@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "Revenue and profit growth",
            ClaimCategory.FINANCIAL.value,
        ),
        (
            "Industry supply and demand",
            ClaimCategory.INDUSTRY.value,
        ),
        (
            "Company valuation is attractive",
            ClaimCategory.VALUATION.value,
        ),
        (
            "Business revenue and customers",
            ClaimCategory.BUSINESS.value,
        ),
        (
            "Future growth outlook",
            ClaimCategory.GROWTH.value,
        ),
        (
            "Market risk is increasing",
            ClaimCategory.RISK.value,
        ),
        (
            "The company recommends buying shares",
            ClaimCategory.INVESTMENT.value,
        ),
    ],
)
def test_classify_category(
    validator,
    text,
    expected,
):

    result = validator.classify_category(
        text
    )

    assert result == expected


def test_unknown_category(
    validator,
):

    result = validator.classify_category(
        "A completely unrelated statement."
    )

    assert result == ClaimCategory.OTHER.value


# ============================================================
# Direction classification tests
# ============================================================

def test_classify_positive_direction(
    validator,
):

    result = validator.classify_direction(
        "Revenue growth is strong and demand is increasing."
    )

    assert result == ClaimDirection.POSITIVE.value


def test_classify_negative_direction(
    validator,
):

    result = validator.classify_direction(
        "Revenue is declining and the business is weak."
    )

    assert result == ClaimDirection.NEGATIVE.value


def test_classify_neutral_direction(
    validator,
):

    result = validator.classify_direction(
        "The company operates in the optical industry."
    )

    assert result == ClaimDirection.NEUTRAL.value


def test_classify_chinese_positive_direction(
    validator,
):

    result = validator.classify_direction(
        "公司营收增长，市场需求持续上升。"
    )

    assert result == ClaimDirection.POSITIVE.value


def test_classify_chinese_negative_direction(
    validator,
):

    result = validator.classify_direction(
        "公司收入下降，市场需求下滑。"
    )

    assert result == ClaimDirection.NEGATIVE.value


# ============================================================
# Evidence extraction tests
# ============================================================

def test_extract_url_evidence(
    validator,
):

    references = validator.extract_evidence_references(
        "Source: https://example.com/report"
    )

    assert any(
        "https://example.com/report" in item
        for item in references
    )


def test_extract_year_evidence(
    validator,
):

    references = validator.extract_evidence_references(
        "According to the annual report 2025."
    )

    assert "2025" in references


def test_extract_percentage_evidence(
    validator,
):

    references = validator.extract_evidence_references(
        "Revenue increased by 25%."
    )

    assert "25%" in references


def test_extract_evidence_removes_duplicates(
    validator,
):

    references = validator.extract_evidence_references(
        "Revenue increased by 25%. Revenue increased by 25%."
    )

    assert len(references) == len(
        set(references)
    )


def test_assess_strong_evidence(
    validator,
):

    result = validator.assess_evidence(
        claim_text=(
            "Revenue increased by 25%."
        ),
        evidence_section=(
            "According to annual report 2025."
        ),
    )

    assert result == EvidenceLevel.STRONG.value


def test_assess_moderate_evidence(
    validator,
):

    result = validator.assess_evidence(
        claim_text="Revenue increased by 25%."
    )

    assert result == EvidenceLevel.MODERATE.value


def test_assess_missing_evidence(
    validator,
):

    result = validator.assess_evidence(
        claim_text="The company has strong potential."
    )

    assert result == EvidenceLevel.MISSING.value


def test_assess_weak_evidence(
    validator,
):

    result = validator.assess_evidence(
        claim_text="The company has strong potential.",
        evidence_section="According to industry research.",
        evidence_references=["Industry research"],
    )

    assert result == EvidenceLevel.WEAK.value


# ============================================================
# Claim extraction tests
# ============================================================

def test_extract_claims(
    validator,
    bullish_report,
):

    claims = validator.extract_claims(
        agent_id="chatgpt",
        content=bullish_report,
    )

    assert len(claims) > 0

    assert all(
        isinstance(item, ExtractedClaim)
        for item in claims
    )


def test_extract_claim_agent_id(
    validator,
    bullish_report,
):

    claims = validator.extract_claims(
        agent_id="grok",
        content=bullish_report,
    )

    assert all(
        claim.agent_id == "grok"
        for claim in claims
    )


def test_extract_claim_categories(
    validator,
    bullish_report,
):

    claims = validator.extract_claims(
        agent_id="chatgpt",
        content=bullish_report,
    )

    categories = {
        claim.category
        for claim in claims
    }

    assert len(categories) > 0


def test_extract_claim_directions(
    validator,
    bullish_report,
):

    claims = validator.extract_claims(
        agent_id="chatgpt",
        content=bullish_report,
    )

    directions = {
        claim.direction
        for claim in claims
    }

    assert (
        ClaimDirection.POSITIVE.value
        in directions
    )


def test_extract_claim_evidence_level(
    validator,
    bullish_report,
):

    claims = validator.extract_claims(
        agent_id="chatgpt",
        content=bullish_report,
    )

    assert all(
        claim.evidence_level in {
            "strong",
            "moderate",
            "weak",
            "missing",
        }
        for claim in claims
    )


def test_extract_claim_limit(
    task_manager,
    report_collector,
    tmp_path,
):

    validator = CrossValidator(
        task_manager=task_manager,
        report_collector=report_collector,
        storage_dir=tmp_path / "validation",
        max_claims_per_agent=2,
    )

    content = """
Revenue growth is strong.
Industry demand is increasing.
Business expansion is positive.
Valuation remains attractive.
"""

    claims = validator.extract_claims(
        agent_id="chatgpt",
        content=content,
    )

    assert len(claims) <= 2


def test_extract_claim_rejects_invalid_agent_id(
    validator,
):

    with pytest.raises(ValueError):

        validator.extract_claims(
            agent_id="../invalid",
            content="Revenue growth is strong.",
        )


def test_extract_claim_rejects_non_string_content(
    validator,
):

    with pytest.raises(
        CrossValidationReportError
    ):

        validator.extract_claims(
            agent_id="chatgpt",
            content=None,
        )


# ============================================================
# Report analysis tests
# ============================================================

def test_analyze_report(
    validator,
    report_collector,
    research_task,
    bullish_report,
):

    record = submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    analysis = validator.analyze_report(
        record
    )

    assert isinstance(
        analysis,
        AgentReportAnalysis,
    )

    assert analysis.agent_id == "chatgpt"

    assert len(analysis.claims) > 0


def test_analyze_report_quality_score(
    validator,
    report_collector,
    research_task,
    bullish_report,
):

    record = submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    analysis = validator.analyze_report(
        record
    )

    assert 0 <= analysis.quality_score <= 100

    assert 0 <= analysis.evidence_score <= 100


def test_analyze_report_extracts_sections(
    validator,
    report_collector,
    research_task,
    bullish_report,
):

    record = submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    analysis = validator.analyze_report(
        record
    )

    assert "key_findings" in analysis.sections
    assert "evidence" in analysis.sections
    assert "conclusion" in analysis.sections


def test_analyze_report_extracts_evidence_references(
    validator,
    report_collector,
    research_task,
    bullish_report,
):

    record = submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    analysis = validator.analyze_report(
        record
    )

    assert len(
        analysis.evidence_references
    ) > 0


def test_analyze_report_identifies_missing_sections(
    validator,
    report_collector,
    research_task,
):

    content = """
# Executive Summary

A short report.

# Key Findings

Revenue growth is strong.
"""

    record = submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        content,
    )

    analysis = validator.analyze_report(
        record
    )

    assert any(
        "Evidence section is missing" in warning
        for warning in analysis.warnings
    )

    assert any(
        "Independent conclusion section is missing" in warning
        for warning in analysis.warnings
    )


# ============================================================
# Claim similarity tests
# ============================================================

def make_claim(
    claim_id,
    agent_id,
    text,
    category=ClaimCategory.INDUSTRY.value,
    direction=ClaimDirection.POSITIVE.value,
    evidence_level=EvidenceLevel.MODERATE.value,
):

    return ExtractedClaim(
        claim_id=claim_id,
        agent_id=agent_id,
        text=text,
        category=category,
        direction=direction,
        section="test",
        evidence_level=evidence_level,
        confidence=0.7,
        keywords=[],
    )


def make_analysis(
    agent_id,
    claims,
):

    return AgentReportAnalysis(
        report_id=f"REPORT-{agent_id}",
        task_id="TASK-001",
        agent_id=agent_id,
        title=f"{agent_id} test report",
        claims=claims,
        sections={},
        evidence_references=[],
        quality_score=70.0,
        evidence_score=70.0,
        warnings=[],
    )


def test_claim_similarity_identical_claims(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is increasing",
    )

    similarity = validator.claim_similarity(
        claim_a,
        claim_b,
    )

    assert similarity == 1.0


def test_claim_similarity_unrelated_claims(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Company debt pressure is rising",
        category=ClaimCategory.FINANCIAL.value,
    )

    similarity = validator.claim_similarity(
        claim_a,
        claim_b,
    )

    assert similarity == 0.0


def test_claim_similarity_is_between_zero_and_one(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication demand is strong",
    )

    similarity = validator.claim_similarity(
        claim_a,
        claim_b,
    )

    assert 0.0 <= similarity <= 1.0


# ============================================================
# Conflict detection tests
# ============================================================

def test_detect_opposing_claim_conflict(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
        direction=ClaimDirection.POSITIVE.value,
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is declining",
        direction=ClaimDirection.NEGATIVE.value,
    )

    analysis_a = make_analysis(
        "chatgpt",
        [claim_a],
    )

    analysis_b = make_analysis(
        "grok",
        [claim_b],
    )

    conflicts = validator.detect_conflicts(
        [
            analysis_a,
            analysis_b,
        ]
    )

    assert len(conflicts) == 1

    assert conflicts[0].agent_a == "chatgpt"
    assert conflicts[0].agent_b == "grok"


def test_conflict_severity_for_investment_claims(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "The investment recommendation is buy",
        category=ClaimCategory.INVESTMENT.value,
        direction=ClaimDirection.POSITIVE.value,
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "The investment recommendation is sell",
        category=ClaimCategory.INVESTMENT.value,
        direction=ClaimDirection.NEGATIVE.value,
    )

    analysis_a = make_analysis(
        "chatgpt",
        [claim_a],
    )

    analysis_b = make_analysis(
        "grok",
        [claim_b],
    )

    conflicts = validator.detect_conflicts(
        [
            analysis_a,
            analysis_b,
        ]
    )

    assert len(conflicts) == 1

    assert conflicts[0].severity == (
        ConflictSeverity.HIGH.value
    )


def test_same_direction_is_not_conflict(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
        direction=ClaimDirection.POSITIVE.value,
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is strong",
        direction=ClaimDirection.POSITIVE.value,
    )

    analysis_a = make_analysis(
        "chatgpt",
        [claim_a],
    )

    analysis_b = make_analysis(
        "grok",
        [claim_b],
    )

    conflicts = validator.detect_conflicts(
        [
            analysis_a,
            analysis_b,
        ]
    )

    assert conflicts == []


def test_conflict_requires_same_category(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
        category=ClaimCategory.INDUSTRY.value,
        direction=ClaimDirection.POSITIVE.value,
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is declining",
        category=ClaimCategory.FINANCIAL.value,
        direction=ClaimDirection.NEGATIVE.value,
    )

    analysis_a = make_analysis(
        "chatgpt",
        [claim_a],
    )

    analysis_b = make_analysis(
        "grok",
        [claim_b],
    )

    conflicts = validator.detect_conflicts(
        [
            analysis_a,
            analysis_b,
        ]
    )

    assert conflicts == []


def test_conflict_finding_has_explanation(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
        direction=ClaimDirection.POSITIVE.value,
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is declining",
        direction=ClaimDirection.NEGATIVE.value,
    )

    conflicts = validator.detect_conflicts(
        [
            make_analysis("chatgpt", [claim_a]),
            make_analysis("grok", [claim_b]),
        ]
    )

    assert len(conflicts) == 1

    assert conflicts[0].explanation
    assert conflicts[0].resolution_required is True


# ============================================================
# Consensus detection tests
# ============================================================

def test_detect_three_agent_consensus(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is increasing",
    )

    claim_c = make_claim(
        "C1",
        "hark",
        "Optical communication industry demand is increasing",
    )

    analyses = [
        make_analysis("chatgpt", [claim_a]),
        make_analysis("grok", [claim_b]),
        make_analysis("hark", [claim_c]),
    ]

    consensus = validator.detect_consensus(
        analyses
    )

    assert len(consensus) >= 1

    assert consensus[0].support_count == 3

    assert set(
        consensus[0].agents
    ) == {
        "chatgpt",
        "grok",
        "hark",
    }


def test_consensus_requires_minimum_agents(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is increasing",
    )

    analyses = [
        make_analysis("chatgpt", [claim_a]),
        make_analysis("grok", [claim_b]),
    ]

    consensus = validator.detect_consensus(
        analyses
    )

    assert len(consensus) >= 1


def test_unrelated_claims_do_not_form_consensus(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Company debt pressure is rising",
        category=ClaimCategory.FINANCIAL.value,
        direction=ClaimDirection.NEGATIVE.value,
    )

    claim_c = make_claim(
        "C1",
        "hark",
        "Customer concentration is increasing",
        category=ClaimCategory.BUSINESS.value,
    )

    analyses = [
        make_analysis("chatgpt", [claim_a]),
        make_analysis("grok", [claim_b]),
        make_analysis("hark", [claim_c]),
    ]

    consensus = validator.detect_consensus(
        analyses
    )

    assert consensus == []


def test_consensus_contains_supporting_claims(
    validator,
):

    claims = [
        make_claim(
            "A1",
            "chatgpt",
            "Optical communication industry demand is increasing",
        ),
        make_claim(
            "B1",
            "grok",
            "Optical communication industry demand is increasing",
        ),
        make_claim(
            "C1",
            "hark",
            "Optical communication industry demand is increasing",
        ),
    ]

    analyses = [
        make_analysis(
            claim.agent_id,
            [claim],
        )
        for claim in claims
    ]

    consensus = validator.detect_consensus(
        analyses
    )

    assert len(consensus) == 1

    assert len(
        consensus[0].supporting_claims
    ) == 3


# ============================================================
# Pairwise comparison tests
# ============================================================

def test_compare_agents(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
        direction=ClaimDirection.POSITIVE.value,
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is increasing",
        direction=ClaimDirection.POSITIVE.value,
    )

    analysis_a = make_analysis(
        "chatgpt",
        [claim_a],
    )

    analysis_b = make_analysis(
        "grok",
        [claim_b],
    )

    comparison = validator.compare_agents(
        analysis_a,
        analysis_b,
    )

    assert comparison.agent_a == "chatgpt"
    assert comparison.agent_b == "grok"

    assert len(
        comparison.common_claims
    ) == 1


def test_compare_agents_detects_conflict(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
        direction=ClaimDirection.POSITIVE.value,
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is declining",
        direction=ClaimDirection.NEGATIVE.value,
    )

    comparison = validator.compare_agents(
        make_analysis("chatgpt", [claim_a]),
        make_analysis("grok", [claim_b]),
    )

    assert comparison.conflict_count == 1

    assert len(
        comparison.conflicting_claims
    ) == 1


def test_compare_agents_detects_unmatched_claims(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Company debt pressure is rising",
        category=ClaimCategory.FINANCIAL.value,
        direction=ClaimDirection.NEGATIVE.value,
    )

    comparison = validator.compare_agents(
        make_analysis("chatgpt", [claim_a]),
        make_analysis("grok", [claim_b]),
    )

    assert len(
        comparison.unmatched_claims
    ) == 2


def test_agreement_score_is_bounded(
    validator,
):

    claim_a = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    claim_b = make_claim(
        "B1",
        "grok",
        "Optical communication industry demand is increasing",
    )

    comparison = validator.compare_agents(
        make_analysis("chatgpt", [claim_a]),
        make_analysis("grok", [claim_b]),
    )

    assert 0 <= comparison.agreement_score <= 100


# ============================================================
# Full task validation tests
# ============================================================

def test_validate_task_with_three_reports(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
    neutral_report,
):

    submit_three_reports(
        report_collector,
        research_task.task_id,
        bullish_report,
        bearish_report,
        neutral_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    assert isinstance(
        result,
        CrossValidationResult,
    )

    assert result.task_id == research_task.task_id

    assert result.report_count == 3

    assert len(
        result.agent_analyses
    ) == 3


def test_validate_task_generates_validation_id(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    assert result.validation_id.startswith(
        "VAL-"
    )


def test_validate_task_detects_conflicts(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
    neutral_report,
):

    submit_three_reports(
        report_collector,
        research_task.task_id,
        bullish_report,
        bearish_report,
        neutral_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    assert len(result.conflicts) > 0


def test_validate_task_has_quality_scores(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
    neutral_report,
):

    submit_three_reports(
        report_collector,
        research_task.task_id,
        bullish_report,
        bearish_report,
        neutral_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    assert 0 <= result.overall_quality_score <= 100

    assert 0 <= result.overall_evidence_score <= 100

    assert 0 <= result.agreement_score <= 100


def test_validate_task_has_metadata(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
    neutral_report,
):

    submit_three_reports(
        report_collector,
        research_task.task_id,
        bullish_report,
        bearish_report,
        neutral_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    assert result.metadata["task_title"] == (
        research_task.title
    )

    assert result.metadata["algorithm"] == (
        "deterministic_heuristic_v1"
    )

    assert result.metadata["semantic_verification"] is False


def test_validate_task_rejects_invalid_task_id(
    validator,
):

    with pytest.raises(ValueError):

        validator.validate_task(
            "../invalid"
        )


def test_validate_task_requires_at_least_two_reports(
    validator,
    report_collector,
    research_task,
    bullish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    with pytest.raises(
        InsufficientReportsError
    ):

        validator.validate_task(
            research_task.task_id
        )


def test_validate_task_with_custom_min_reports(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    with pytest.raises(
        InsufficientReportsError
    ):

        validator.validate_task(
            research_task.task_id,
            min_reports=3,
        )


def test_validate_task_rejects_invalid_min_reports(
    validator,
    research_task,
):

    with pytest.raises(ValueError):

        validator.validate_task(
            research_task.task_id,
            min_reports=0,
        )


def test_validate_task_rejects_boolean_min_reports(
    validator,
    research_task,
):

    with pytest.raises(ValueError):

        validator.validate_task(
            research_task.task_id,
            min_reports=True,
        )


# ============================================================
# Persistence tests
# ============================================================

def test_save_result(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    path = validator.save_result(
        result
    )

    assert path.exists()

    assert path.suffix == ".json"


def test_validate_task_persists_result(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    import json
    from pathlib import Path

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )
    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )
    result = validator.validate_task(research_task.task_id)
    result_path = result.metadata["result_path"]
    assert result_path
    path = Path(result_path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert "validation_id" in payload


def test_saved_result_is_valid_json(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    path = validator.save_result(
        result
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    assert data["task_id"] == research_task.task_id

    assert data["validation_id"] == result.validation_id


def test_get_result(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    validator.save_result(
        result
    )

    loaded = validator.get_result(
        result.validation_id
    )

    assert loaded["validation_id"] == (
        result.validation_id
    )

    assert loaded["task_id"] == (
        research_task.task_id
    )


def test_get_missing_result_raises(
    validator,
):

    with pytest.raises(
        ValidationResultNotFoundError
    ):

        validator.get_result(
            "VAL-NOT-EXIST"
        )


def test_list_results(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    validator.save_result(
        result
    )

    results = validator.list_results()

    assert len(results) == 1

    assert results[0]["validation_id"] == (
        result.validation_id
    )


def test_list_results_filters_by_task(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    validator.save_result(
        result
    )

    results = validator.list_results(
        task_id=research_task.task_id
    )

    assert len(results) == 1

    assert results[0]["task_id"] == (
        research_task.task_id
    )


def test_list_results_returns_empty_for_other_task(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    validator.save_result(
        result
    )

    results = validator.list_results(
        task_id="OTHER-TASK"
    )

    assert results == []


# ============================================================
# Debate Engine integration tests
# ============================================================

def test_export_debate_payload(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
    neutral_report,
):

    submit_three_reports(
        report_collector,
        research_task.task_id,
        bullish_report,
        bearish_report,
        neutral_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    payload = validator.export_debate_payload(
        result
    )

    assert payload["task_id"] == (
        research_task.task_id
    )

    assert payload["validation_id"] == (
        result.validation_id
    )

    assert "conflicts" in payload
    assert "consensus" in payload
    assert "agent_analyses" in payload
    assert "agreement_score" in payload


def test_debate_payload_contains_agent_claims(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
    neutral_report,
):

    submit_three_reports(
        report_collector,
        research_task.task_id,
        bullish_report,
        bearish_report,
        neutral_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    payload = validator.export_debate_payload(
        result
    )

    assert len(
        payload["agent_analyses"]
    ) == 3

    for analysis in payload["agent_analyses"]:

        assert "agent_id" in analysis
        assert "claims" in analysis
        assert "quality_score" in analysis
        assert "evidence_score" in analysis


def test_debate_payload_requires_debate_when_conflicts_exist(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
    neutral_report,
):

    submit_three_reports(
        report_collector,
        research_task.task_id,
        bullish_report,
        bearish_report,
        neutral_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    payload = validator.export_debate_payload(
        result
    )

    if result.conflicts:

        assert payload["requires_debate"] is True

    else:

        assert payload["requires_debate"] is False


def test_debate_payload_rejects_invalid_result(
    validator,
):

    with pytest.raises(ValueError):

        validator.export_debate_payload(
            {}
        )


# ============================================================
# Serialization tests
# ============================================================

def test_claim_to_dict():

    claim = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    data = claim.to_dict()

    assert data["claim_id"] == "A1"
    assert data["agent_id"] == "chatgpt"
    assert data["category"] == ClaimCategory.INDUSTRY.value


def test_analysis_to_dict():

    claim = make_claim(
        "A1",
        "chatgpt",
        "Optical communication industry demand is increasing",
    )

    analysis = make_analysis(
        "chatgpt",
        [claim],
    )

    data = analysis.to_dict()

    assert data["agent_id"] == "chatgpt"

    assert len(data["claims"]) == 1


def test_result_to_dict(
    validator,
    report_collector,
    research_task,
    bullish_report,
    bearish_report,
):

    submit_report(
        report_collector,
        research_task.task_id,
        "chatgpt",
        bullish_report,
    )

    submit_report(
        report_collector,
        research_task.task_id,
        "grok",
        bearish_report,
    )

    result = validator.validate_task(
        research_task.task_id
    )

    data = result.to_dict()

    assert data["task_id"] == research_task.task_id

    assert "agent_analyses" in data

    assert "conflicts" in data

    assert "consensus" in data

    # The result must be JSON serializable.
    serialized = json.dumps(
        data,
        ensure_ascii=False,
    )

    assert serialized


# ============================================================
# Regression and boundary tests
# ============================================================

def test_empty_analyses_have_no_conflicts(
    validator,
):

    conflicts = validator.detect_conflicts(
        []
    )

    assert conflicts == []


def test_empty_analyses_have_no_consensus(
    validator,
):

    consensus = validator.detect_consensus(
        []
    )

    assert consensus == []


def test_empty_pairwise_comparison(
    validator,
):

    comparison = validator.compare_agents(
        make_analysis("chatgpt", []),
        make_analysis("grok", []),
    )

    assert comparison.common_claims == []

    assert comparison.conflicting_claims == []

    assert comparison.unmatched_claims == []

    assert comparison.agreement_score == 0.0


def test_score_is_bounded(
    validator,
):

    assert validator._score(-10) == 0.0

    assert validator._score(50) == 50.0

    assert validator._score(150) == 100.0


def test_result_path_rejects_path_traversal(
    validator,
):

    with pytest.raises(ValueError):

        validator._result_path(
            "../outside"
        )


def test_get_result_rejects_path_traversal(
    validator,
):

    with pytest.raises(ValueError):

        validator.get_result(
            "../outside"
        )


def test_list_results_rejects_invalid_task_id(
    validator,
):

    with pytest.raises(ValueError):

        validator.list_results(
            task_id="../outside"
        )


# ============================================================
# End of test suite
# ============================================================


def test_single_seat_marks_not_performed(
    task_manager, research_task, report_collector, bullish_report
):
    validator = CrossValidator(task_manager, report_collector, min_reports=1)
    submit_report(report_collector, research_task.task_id, "chatgpt", bullish_report)
    result = validator.validate_task(research_task.task_id)
    assert result.status == "not_performed"
    assert any(w.startswith("Multi-AI not performed") for w in result.warnings)


def test_missing_seat_is_disclosed(
    task_manager, research_task, report_collector, bullish_report, bearish_report
):
    validator = CrossValidator(task_manager, report_collector)
    submit_report(report_collector, research_task.task_id, "chatgpt", bullish_report)
    submit_report(report_collector, research_task.task_id, "grok", bearish_report)
    result = validator.validate_task(research_task.task_id)
    assert result.status != "not_performed"
    assert any(w.startswith("Seats not reporting") for w in result.warnings)

def test_unsourced_seats_are_excluded_from_consensus(
    research_task, report_collector, validator, bullish_report,
    bearish_report
):
    source = {
        "name": "Official company filing",
        "url": "https://example.com/report",
        "published_at": "2026-11-17T10:00:00+08:00",
        "data_period": "2026Q3",
        "source_type": "company_filing",
        "verification_status": "verified",
    }
    report_collector.collect_report(
        task_id=research_task.task_id,
        agent_id="chatgpt",
        content=bullish_report,
        sources=[source],
    )
    submit_report(report_collector, research_task.task_id, "grok", bearish_report)
    submit_report(report_collector, research_task.task_id, "hark", bullish_report)


    result = validator.validate_task(research_task.task_id)
    metadata = result.metadata
    assert metadata["seats_sourced"] == ["chatgpt"]
    assert set(metadata["seats_unsourced"]) == {"grok", "hark"}
    assert any(
        warning.startswith("Seats excluded from consensus")
        for warning in result.warnings
    )