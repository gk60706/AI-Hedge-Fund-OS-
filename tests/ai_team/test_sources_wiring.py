import json

from types import SimpleNamespace

from ai_team.adapters import build_registry, generate_reports
from ai_team.research_pipeline import AgentReport


def test_generated_report_carries_sources(tmp_path):
    source = {
        "name": "Ann",
        "url": "https://example.com/a",
        "published_at": "2026-08-15T10:00:00+08:00",
        "data_period": "2026-Q2",
        "source_type": "company_filing",
        "verification_status": "verified",
    }
    content = (
        "## Executive Summary\n"
        + "Company research and financial analysis. " * 30
        + "\n## Business Analysis\n"
        + "Revenue and growth outlook. " * 30
        + '\n```json\n{"sources":[' + json.dumps(source) + "]}\n```"
    )

    class Transport:
        def __call__(self, url, headers, payload, timeout):
            return {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ]
            }

    registry = build_registry(
        env={"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"},
        env_file=tmp_path / "missing.env",
        transport=Transport(),
    )
    reports, failures = generate_reports(
        registry,
        task_id="T1",
        subject="300394",
        ticker="300394",
        as_of_date="2026-11-17",
        only=["chatgpt"],
    )

    assert not failures
    assert reports[0].sources == [source]
    assert reports[0].to_dict()["sources"] is not None


def test_agent_report_sources_default_none():
    assert AgentReport(agent_id="chatgpt", title="t", content="c").sources is None
    sources = [{"name": "x"}]
    assert (
        AgentReport(agent_id="chatgpt", title="t", content="c", sources=sources).sources
        == sources
    )


def test_aggregate_evidence_contract_empty_returns_none():
    from ai_team.research_pipeline import _aggregate_evidence_contract

    assert _aggregate_evidence_contract([]) is None


def test_aggregate_evidence_contract_mixes_reports():
    from ai_team.research_pipeline import _aggregate_evidence_contract

    records = [
        SimpleNamespace(
            validation={
                "evidence_contract": {
                    "status": "validated",
                    "valid": True,
                    "source_count": 2,
                    "verified_count": 1,
                    "unverified_count": 1,
                }
            }
        ),
        SimpleNamespace(
            validation={
                "evidence_contract": {
                    "status": "not_provided",
                    "valid": None,
                }
            }
        ),
    ]

    result = _aggregate_evidence_contract(records)

    assert result["status"] == "partial"
    assert result["valid"] is False
    assert result["source_count"] == 2
    assert result["verified_count"] == 1
    assert result["unverified_count"] == 1
    assert result["unverified_report_count"] == 1
    assert result["report_count"] == 2
