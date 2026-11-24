"""Offline tests for ai_team.providers (no network)."""
from __future__ import annotations

import textwrap

import pytest

from ai_team.adapters import AdapterConfigError
from ai_team.providers import (
    ProviderConfig,
    build_custom_registry,
    describe_providers,
    expand_env,
    load_providers,
)

SECRET = "sk-test-secret-1234567890"


def _write(tmp_path, body: str):
    path = tmp_path / "ai_providers.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _one(**fields) -> str:
    base = {"provider_id": "p1", "base_url": "https://api.example.com/v1", "model": "m1"}
    base.update(fields)
    lines = ["providers:"]
    first = True
    for key, value in base.items():
        if value is None:
            continue
        prefix = "  - " if first else "    "
        lines.append(f"{prefix}{key}: {value}")
        first = False
    return "\n".join(lines) + "\n"


# 1) expand_env
def test_expand_env_variants():
    env = {"A": "hello", "EMPTY": ""}
    assert expand_env("${A}", env) == "hello"
    assert expand_env("${NOPE:-dflt}", env) == "dflt"
    assert expand_env("${EMPTY:-dflt}", env) == "dflt"
    assert expand_env("${MISSING}", env) == ""


# 2) load_providers happy path
def test_load_providers_parses_two(tmp_path):
    path = _write(tmp_path, """
        providers:
          - provider_id: deepseek
            display_name: DeepSeek
            base_url: "${DS_URL:-https://api.deepseek.com/v1}"
            model: deepseek-chat
          - provider_id: kimi
            base_url: https://api.moonshot.cn/v1
            model: kimi-k2
            api_key_env: MY_KIMI_KEY
            tags: [cn]
    """)
    providers = load_providers(path, env={})
    assert len(providers) == 2
    assert all(isinstance(p, ProviderConfig) for p in providers)
    ds, kimi = providers
    assert ds.base_url == "https://api.deepseek.com/v1"
    assert ds.api_key_env == "AIH_DEEPSEEK_API_KEY"
    assert kimi.api_key_env == "MY_KIMI_KEY"
    assert kimi.tags == ("cn",)


# 3) load_providers errors
BAD_CASES = {
    "duplicate_id": """
        providers:
          - {provider_id: a, base_url: "https://x/v1", model: m}
          - {provider_id: a, base_url: "https://y/v1", model: m}
    """,
    "missing_base_url": _one(base_url=None),
    "missing_model": _one(model=None),
    "top_not_dict": "- just\n- a list\n",
    "providers_not_list": "providers: {a: 1}\n",
    "timeout_zero": _one(timeout=0),
    "max_tokens_zero": _one(max_tokens=0),
    "max_tokens_too_big": _one(max_tokens=40000),
    "temperature_three": _one(temperature=3),
    "enabled_not_bool": _one(enabled='"yes"'),
    "tags_number": _one(tags=5),
}


@pytest.mark.parametrize("body", list(BAD_CASES.values()), ids=list(BAD_CASES))
def test_load_providers_rejects(tmp_path, body):
    path = _write(tmp_path, body)
    with pytest.raises(AdapterConfigError):
        load_providers(path, env={})


# 4) build_custom_registry
REGISTRY_YAML = """
    providers:
      - {provider_id: haskey, base_url: "https://a.example.com/v1", model: m1}
      - {provider_id: nokey, base_url: "https://b.example.com/v1", model: m2}
      - {provider_id: paused, base_url: "https://c.example.com/v1", model: m3, enabled: false}
      - {provider_id: claude, base_url: "https://d.example.com/v1", model: m4, protocol: anthropic}
"""
ENV = {"AIH_HASKEY_API_KEY": SECRET, "AIH_CLAUDE_API_KEY": SECRET}


def test_build_custom_registry_routes(tmp_path):
    registry = build_custom_registry(_write(tmp_path, REGISTRY_YAML), env=ENV)
    assert "haskey" in registry.adapters
    assert "missing:" in registry.skipped["nokey"]
    assert "paused" not in registry.adapters and "paused" not in registry.skipped
    assert "unsupported protocol" in registry.skipped["claude"]


# 5) describe_providers
def test_describe_providers_statuses_and_no_secret(tmp_path):
    path = _write(tmp_path, REGISTRY_YAML)
    rows = describe_providers(build_custom_registry(path, env=ENV), load_providers(path, env=ENV))
    assert all(isinstance(r, dict) for r in rows)
    by_id = {r["provider_id"]: r for r in rows}
    assert by_id["haskey"]["status"] == "available"
    assert by_id["nokey"]["status"].startswith("skipped:")
    for row in rows:
        assert "api_key" not in row
        assert SECRET not in repr(row)


# 6) injected transport + endpoint
def test_adapter_endpoint_with_injected_transport(tmp_path, monkeypatch):
    calls = []

    def fake_transport(url, headers, payload, timeout):
        calls.append(url)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setenv("AIH_HASKEY_API_KEY", SECRET)
    path = _write(tmp_path, REGISTRY_YAML)
    registry = build_custom_registry(path, env=None, transport=fake_transport)
    adapter = registry.adapters["haskey"]
    assert adapter.endpoint == "https://a.example.com/v1" + "/chat/completions"
    assert calls == []  # building the registry never touches the network
