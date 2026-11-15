# tests/ai_team/test_research_pipeline.py

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_team.research_pipeline import (
    AgentReport,
    DebateContribution,
    V310ResearchPipeline,
)


SYMBOL = "300394"

REPORT_TEMPLATE = """# Executive Summary

The company is {stance} under the current evidence set.

# Key Findings

- Finding one: industry demand needs order-level confirmation.
- Finding two: margin trend should be verified against disclosures.

# Evidence and Sources

- Evidence: public disclosures and industry data.
- Evidence: no live quote or real-time data is used here.

# Analytical Reasoning

Industry growth does not automatically translate into earnings growth;
capacity, product mix, and customer concentration also matter.

# Risks and Limitations

- Demand may slow.
- Valuation may already price in optimistic expectations.

# Independent Conclusion

{conclusion}

# Confidence Level

{confidence}
"""


def _reports() -> list[AgentReport]:
    return [
        AgentReport(
            agent_id="chatgpt",
            title="CIO research report",
            content=REPORT_TEMPLATE.format(
                stance="worth monitoring",
                conclusion="Maintain a watch position.",
                confidence="0.72",
            ),
        ),
        AgentReport(
            agent_id="grok",
            title="Market intelligence report",
            content=REPORT_TEMPLATE.format(
                stance="constructive but unconfirmed",
                conclusion="Continue monitoring pending order data.",
                confidence="0.76",
            ),
        ),
        AgentReport(
            agent_id="hark",
            title="Analyst research report",
            content=REPORT_TEMPLATE.format(
                stance="neutral",
                conclusion="No unconditional investment conclusion yet.",
                confidence="0.68",
            ),
        ),
    ]


def _contributions() -> list[DebateContribution]:
    return [
        DebateContribution(
            agent_id="chatgpt",
            position="neutral",
            content="Valuation needs confirmation from earnings.",
            evidence=["Illustrative evidence only."],
        ),
        DebateContribution(
            agent_id="grok",
            position="support",
            content="Industry demand is a positive research direction.",
            evidence=["Illustrative evidence only."],
        ),
        DebateContribution(
            agent_id="hark",
            position="neutral",
            content="Continue monitoring, evidence is not conclusive.",
            evidence=["Illustrative evidence only."],
        ),
    ]


def _ballots() -> list[dict[str, object]]:
    return [
        {
            "member_id": member_id,
            "vote": "approve",
            "rationale": "Research-only approval for monitoring.",
        }
        for member_id in (
            "cio",
            "risk",
            "quant",
            "fundamental",
            "industry",
            "compliance",
        )
    ]


@pytest.fixture
def pipeline(tmp_path: Path) -> V310ResearchPipeline:
    return V310ResearchPipeline(project_root=tmp_path)


def test_pipeline_runs_end_to_end(pipeline, tmp_path):
    output = tmp_path / "decision.json"

    outcome = pipeline.run(
        symbol=SYMBOL,
        reports=_reports(),
        contributions=_contributions(),
        conclusion="partial_consensus",
        conclusion_text="Agents agree the name deserves research, not a trade.",
        unresolved_issues=["Verify order growth."],
        rationale="Research-only committee review.",
        ballots=_ballots(),
        artifact_path=output,
    )

    assert outcome.task_id
    assert outcome.decision is not None
    assert output.is_file()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["symbol"] == SYMBOL
    assert payload["decision"]["status"] in {
        "approved",
        "approved_with_conditions",
    }


def test_stage_order_is_enforced(tmp_path):
    fresh = V310ResearchPipeline(project_root=tmp_path / "second")

    with pytest.raises(RuntimeError):
        fresh.convene()

    with pytest.raises(RuntimeError):
        fresh.build_consensus()
