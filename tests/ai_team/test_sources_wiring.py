import json

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
