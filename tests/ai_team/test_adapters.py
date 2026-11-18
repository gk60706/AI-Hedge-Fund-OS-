"""V3.10 API 适配器层测试（完全不联网）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_team.adapters import (
    AdapterConfigError,
    AdapterRateLimitError,
    AdapterResponseError,
    AdapterUnavailableError,
    OpenAICompatibleAdapter,
    build_agent_prompt,
    build_registry,
    generate_reports,
    load_env_file,
    validate_report_sections,
)

REPORT_BODY = """## Executive Summary
Tianfu Communication benefits from 800G/1.6T optical demand.

## Key Findings
- Q3 revenue growth of 31.5% YoY (company filing, Q3 2026, unverified).
- Gross margin 65.1% in Q3 (company filing, Q3 2026, unverified).

## Evidence and Sources
- Q3 2026 quarterly report (unverified, not independently audited here).

## Analytical Reasoning
Growth is capacity-driven, but inventory build (+178.7% YTD) has not yet
converted into revenue, so the conclusion stays conditional.

## Risks and Limitations
- Export-control risk on optical components.
- Operating cash flow at 0.52x net income in Q3 is a warning sign.

## Independent Conclusion
Constructive but conditional; evidence is insufficient for a clean approval.

## Confidence Level
0.72 - cash-flow confirmation is missing.
"""


class RecordingTransport:
    def __init__(self, content: str = REPORT_BODY, fail: bool = False) -> None:
        self.content = content
        self.fail = fail
        self.calls: list[dict] = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append(
            {"url": url, "headers": dict(headers), "payload": payload, "timeout": timeout}
        )
        if self.fail:
            raise AdapterResponseError("HTTP 500 from provider")
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": self.content},
                    "finish_reason": "stop",
                }
            ]
        }


@pytest.fixture
def env():
    return {
        "OPENAI_API_KEY": "sk-test-chatgpt",
        "OPENAI_MODEL": "gpt-5.5",
        "XAI_API_KEY": "xai-test",
        "XAI_MODEL": "grok-test-model",
        "HARK_API_KEY": "",
        "HARK_BASE_URL": "",
        "HARK_MODEL": "",
    }


# ------------------------------------------------------------------
# 配置装配
# ------------------------------------------------------------------


def test_registry_skips_unconfigured_agents(env, tmp_path):
    registry = build_registry(env=env, env_file=tmp_path / "missing.env")

    assert registry.available() == ["chatgpt", "grok"]
    assert "hark" in registry.skipped
    assert "HARK_BASE_URL" in registry.skipped["hark"]
    assert "HARK_MODEL" in registry.skipped["hark"]


def test_registry_requires_grok_model(env, tmp_path):
    env["XAI_MODEL"] = ""
    registry = build_registry(env=env, env_file=tmp_path / "missing.env")

    assert "grok" not in registry.adapters
    assert "XAI_MODEL" in registry.skipped["grok"]


def test_load_env_file_parses_key_values(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# comment\nOPENAI_API_KEY=sk-abc\nXAI_MODEL=\"grok-x\"\n\nEMPTY=\n", encoding="utf-8"
    )

    values = load_env_file(path)

    assert values["OPENAI_API_KEY"] == "sk-abc"
    assert values["XAI_MODEL"] == "grok-x"
    assert values["EMPTY"] == ""


def test_registry_reports_secret_free_description(env, tmp_path):
    registry = build_registry(env=env, env_file=tmp_path / "missing.env")
    described = json.dumps(registry.describe(), ensure_ascii=False)

    assert "sk-test-chatgpt" not in described
    assert "xai-test" not in described
    assert "chatgpt" in described


# ------------------------------------------------------------------
# 单次调用
# ------------------------------------------------------------------


def test_complete_parses_openai_payload(env, tmp_path):
    transport = RecordingTransport()
    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=transport
    )

    text = registry.get("chatgpt").complete("research prompt")

    assert "Executive Summary" in text
    call = transport.calls[0]
    assert call["url"].endswith("/chat/completions")
    assert call["payload"]["model"] == "gpt-5.5"
    assert call["payload"]["messages"][1] == {
        "role": "user",
        "content": "research prompt",
    }
    assert call["headers"]["Authorization"].startswith("Bearer ")


def test_complete_raises_on_http_error(env, tmp_path):
    transport = RecordingTransport(fail=True)
    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=transport
    )

    with pytest.raises(AdapterResponseError, match="HTTP 500"):
        registry.get("chatgpt").complete("prompt")


def test_complete_raises_on_empty_content(env, tmp_path):
    transport = RecordingTransport(content="   ")
    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=transport
    )

    with pytest.raises(AdapterResponseError, match="empty message content"):
        registry.get("chatgpt").complete("prompt")


def test_adapter_rejects_blank_prompt(env, tmp_path):
    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=RecordingTransport()
    )

    with pytest.raises(AdapterConfigError):
        registry.get("chatgpt").complete("  ")


# ------------------------------------------------------------------
# 提示词与报告
# ------------------------------------------------------------------


def test_build_agent_prompt_enforces_contract(env, tmp_path):
    prompt = build_agent_prompt(
        "chatgpt",
        task_id="task-1",
        subject="300394.SZ",
        ticker="300394",
        as_of_date="2026-11-16",
    )

    for section in ("## Executive Summary", "## Confidence Level", "## Risks and Limitations"):
        assert section in prompt
    assert "300394" in prompt
    assert "OUTPUT CONTRACT" in prompt


def test_build_agent_prompt_rejects_unknown_agent():
    with pytest.raises(AdapterConfigError):
        build_agent_prompt(
            "unknown",
            task_id="t",
            subject="s",
            ticker="s",
            as_of_date="2026-11-16",
        )


def test_generate_reports_partial_failure(env, tmp_path):
    ok = RecordingTransport()
    bad = RecordingTransport(fail=True)

    class SwitchTransport:
        def __call__(self, url, headers, payload, timeout):
            if "x.ai" in url:
                return bad(url, headers, payload, timeout)
            return ok(url, headers, payload, timeout)

    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=SwitchTransport()
    )

    reports, failures = generate_reports(
        registry,
        task_id="task-1",
        subject="300394.SZ",
        ticker="300394",
        as_of_date="2026-11-16",
    )

    assert [r.agent_id for r in reports] == ["chatgpt"]
    assert "grok" in failures
    assert "AdapterResponseError" in failures["grok"]
    assert len(reports[0].record.content_sha256) == 64
    assert reports[0].record.response_chars > 0


def test_generate_reports_marks_unconfigured_agents(env, tmp_path):
    env["HARK_BASE_URL"] = ""
    registry = build_registry(env=env, env_file=tmp_path / "missing.env",
                              transport=RecordingTransport())

    reports, failures = generate_reports(
        registry,
        task_id="task-1",
        subject="300394.SZ",
        ticker="300394",
        as_of_date="2026-11-16",
    )

    assert "hark" not in [r.agent_id for r in reports]
    assert "hark" in failures
    assert "HARK_BASE_URL" in failures["hark"]


def test_generate_reports_only_filter(env, tmp_path):
    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=RecordingTransport()
    )

    reports, failures = generate_reports(
        registry,
        task_id="task-1",
        subject="300394.SZ",
        ticker="300394",
        as_of_date="2026-11-16",
        only=["chatgpt"],
    )

    assert [r.agent_id for r in reports] == ["chatgpt"]
    assert failures == {}


def test_validate_report_sections_detects_missing():
    assert validate_report_sections(REPORT_BODY) == []
    assert "Key Findings" in validate_report_sections("## Executive Summary\nonly")


# ------------------------------------------------------------------
# 与流水线集成
# ------------------------------------------------------------------


def test_run_live_collects_reports_without_debate(env, tmp_path):
    from ai_team.research_pipeline import V310ResearchPipeline

    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=RecordingTransport()
    )
    pipeline = V310ResearchPipeline(project_root=tmp_path)

    result = pipeline.run_live(
        symbol="300394.SZ",
        registry=registry,
        as_of_date="2026-11-16",
        reports_dir=tmp_path / "reports",
    )

    assert isinstance(result, dict)
    assert result["stage"] == "reports_collected"
    assert result["reports_collected"] == 2
    assert (tmp_path / "reports" / "chatgpt.md").is_file()
    assert (tmp_path / "reports" / "grok.md").is_file()
    assert (tmp_path / "generation.json").is_file()

    audit = json.loads((tmp_path / "generation.json").read_text(encoding="utf-8"))
    assert audit["symbol"] == "300394.SZ"
    assert len(audit["generated"]) == 2
    assert "sk-test-chatgpt" not in json.dumps(audit)


def test_run_live_records_missing_agent_in_failures(env, tmp_path):
    from ai_team.research_pipeline import V310ResearchPipeline

    env["HARK_BASE_URL"] = ""
    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=RecordingTransport()
    )
    pipeline = V310ResearchPipeline(project_root=tmp_path)

    result = pipeline.run_live(
        symbol="300394.SZ",
        registry=registry,
        as_of_date="2026-11-16",
        reports_dir=tmp_path / "reports",
        allow_missing_agents=True,
    )

    assert result["failed_agents"]
    assert "hark" in result["failed_agents"]


def test_describe_seat_status_lists_skipped_seats():
    from ai_team.adapters import AdapterRegistry, describe_seat_status

    registry = AdapterRegistry(
        adapters={"chatgpt": object()},
        skipped={
            "grok": "missing: XAI_API_KEY",
            "hark": "missing: HARK_MODEL",
        },
    )
    result = describe_seat_status(registry)
    assert "chatgpt=available" in result
    assert "grok=skipped" in result
    assert "Manual import required for: grok, hark" in result
    assert len(result.splitlines()) == 2


def test_http_429_raises_rate_limit_error(monkeypatch):
    import urllib.error
    from email.message import Message

    from ai_team.adapters import _urllib_transport

    def fake_urlopen(request, timeout=None):
        response_headers = Message()
        response_headers["Retry-After"] = "3"
        raise urllib.error.HTTPError(
            "https://example.com", 429, "Too Many Requests", response_headers, None
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(AdapterRateLimitError) as exc:
        _urllib_transport("https://example.com", {}, {}, 5)
    assert exc.value.retry_after == 3.0


def test_429_beyond_cap_records_failure(tmp_path, monkeypatch):
    def transport(url, headers, payload, timeout):
        raise AdapterRateLimitError("HTTP 429 from provider", retry_after=999)

    monkeypatch.setattr(
        "ai_team.adapters.time.sleep",
        lambda _: pytest.fail("unexpected sleep"),
    )
    registry = build_registry(
        env={"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"},
        env_file=tmp_path / "missing.env",
        transport=transport,
    )
    _, failures = generate_reports(
        registry,
        task_id="test",
        subject="test",
        ticker="600000",
        as_of_date="2026-11-18",
        only=["chatgpt"],
    )
    assert "retry_after exceeds cap" in failures["chatgpt"]


@pytest.mark.parametrize("kwargs", [
    {"timeout": 0},
    {"max_tokens": 0},
    {"temperature": 3},
    {"base_url": "ftp://example.com"},
])
def test_adapter_rejects_invalid_boundaries(kwargs):
    from ai_team.adapters import ADAPTER_SPECS, OpenAICompatibleAdapter

    spec = ADAPTER_SPECS["chatgpt"]
    params = {
        "timeout": 5.0, "max_tokens": 16,
        "temperature": 0.3, "base_url": "https://api.openai.com/v1",
    }
    params.update(kwargs)
    with pytest.raises(AdapterConfigError):
        OpenAICompatibleAdapter(
            spec, "test-key", params["base_url"], "test-model",
            timeout=params["timeout"], max_tokens=params["max_tokens"],
            temperature=params["temperature"],
        )


def test_call_budget_skips_remaining_seats(tmp_path, env):
    transport = RecordingTransport()
    registry = build_registry(
        env=env, env_file=tmp_path / "missing.env", transport=transport
    )
    reports, failures = generate_reports(
        registry, task_id="test", subject="test", ticker="600000",
        as_of_date="2026-11-18", only=["chatgpt", "grok"], call_budget=1,
    )
    assert len(reports) == 1
    assert any("call budget exhausted" in error for error in failures.values())


def test_real_provider_response_shapes(tmp_path):
    from ai_team.adapters import AdapterResponseError, build_registry

    payload_stop = {
        "id": "chatcmpl-stop", "object": "chat.completion", "created": 1795000000, "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "公司营收保持稳健增长。"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }
    payload_length = {
        "id": "chatcmpl-length", "object": "chat.completion", "created": 1795000000, "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "公司营收保持稳健增长。"}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }
    payload_error = {"error": {"message": "insufficient_quota", "type": "insufficient_quota"}}
    adapter = build_registry(
        env={"OPENAI_API_KEY": "x", "OPENAI_MODEL": "m"},
        env_file=tmp_path / "missing.env",
    ).adapters["chatgpt"]
    for payload, reason in ((payload_stop, "stop"), (payload_length, "length")):
        content, finish_reason = adapter._extract_text(payload)
        assert content == "公司营收保持稳健增长。"
        assert finish_reason == reason
    with pytest.raises(AdapterResponseError):
        adapter._extract_text(payload_error)


def test_transport_rejects_invalid_json(monkeypatch):
    from ai_team.adapters import AdapterResponseError, _urllib_transport

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"<html>502 Bad Gateway</html>"

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: _FakeResponse()
    )
    with pytest.raises(AdapterResponseError, match="non-JSON"):
        _urllib_transport("https://example.com", {}, {}, 5)
