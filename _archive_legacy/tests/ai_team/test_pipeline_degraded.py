"""V3.10 显式降级（allow_missing_agents=True）回归测试，不联网。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ai_team.adapters as adapters_module
from ai_team.research_pipeline import (
    INCOMPLETE_NOTE_MARKER,
    AgentReport,
    InsufficientAgentsError,
    V310ResearchPipeline,
)

SYMBOL = "300394.SZ"

# 只有两个章节：内容有效，但 quality=incomplete
INCOMPLETE_CONTENT = """# Executive Summary

Qwen2.5-1.5B short answer: demand looks firm, evidence thin.

# Key Findings

- Revenue grew in Q3 2026 per the company filing.
"""


class _FakeRegistry:
    adapters: dict = {}
    skipped = {"chatgpt": "missing: AIH_CHATGPT_API_KEY"}

    def describe(self) -> dict:
        return {"adapters": [], "skipped": dict(self.skipped)}


def _generated(agent_id: str, content: str) -> SimpleNamespace:
    item = SimpleNamespace(
        agent_id=agent_id,
        title=f"{agent_id} live report",
        content=content,
        source="api",
        sources=None,
        record=SimpleNamespace(content_sha256="0" * 64),
    )
    item.to_dict = lambda: {"agent_id": agent_id, "chars": len(content)}
    return item


@pytest.fixture
def pipeline(tmp_path: Path) -> V310ResearchPipeline:
    return V310ResearchPipeline(project_root=tmp_path)


# (a) 0 份报告 + allow_missing：返回降级 dict，不抛异常
def test_run_live_zero_reports_returns_degraded(pipeline, tmp_path, monkeypatch):
    def fake_generate(registry, **kwargs):
        return [], {"chatgpt": "missing: AIH_CHATGPT_API_KEY"}

    monkeypatch.setattr(adapters_module, "generate_reports", fake_generate)

    result = pipeline.run_live(
        SYMBOL,
        _FakeRegistry(),
        as_of_date="2026-11-17",
        reports_dir=tmp_path / "live" / "reports",
        allow_missing_agents=True,
    )

    assert isinstance(result, dict)
    assert result["stage"] == "degraded_no_reports"
    assert result["task_id"] == pipeline.task_id
    assert result["symbol"] == SYMBOL
    assert "chatgpt" in result["failures"]
    assert result["registry"]["skipped"]["chatgpt"].startswith("missing:")
    artifact = Path(result["artifact"])
    assert artifact.is_file()
    assert json.loads(artifact.read_text(encoding="utf-8"))["stage"] == "degraded_no_reports"


# (b) 1 份不完整报告 + allow_missing=True：入库并带 incomplete 标记
def test_incomplete_report_accepted_with_marker(pipeline):
    pipeline.start_task(SYMBOL)

    records = pipeline.submit_reports(
        [AgentReport(agent_id="chatgpt", title="partial", content=INCOMPLETE_CONTENT)],
        allow_missing=True,
    )

    assert len(records) == 1
    record = records[0]
    assert record.quality == "incomplete"
    assert INCOMPLETE_NOTE_MARKER in record.notes
    assert pipeline.agent_failures == {}


def test_run_live_one_incomplete_report_degrades(pipeline, tmp_path, monkeypatch):
    def fake_generate(registry, **kwargs):
        return [_generated("chatgpt", INCOMPLETE_CONTENT)], {}

    monkeypatch.setattr(adapters_module, "generate_reports", fake_generate)

    result = pipeline.run_live(
        SYMBOL,
        _FakeRegistry(),
        as_of_date="2026-11-17",
        reports_dir=tmp_path / "live" / "reports",
        allow_missing_agents=True,
    )

    assert result["stage"] == "degraded_insufficient_reports"
    assert result["reports_collected"] == 1
    assert result["validation"] == "not_performed"


# (c) allow_missing=False：行为不变，不完整报告被拒，仍抛 InsufficientAgentsError
def test_strict_mode_still_raises(pipeline):
    pipeline.start_task(SYMBOL)

    with pytest.raises(InsufficientAgentsError):
        pipeline.submit_reports(
            [AgentReport(agent_id="chatgpt", title="partial", content=INCOMPLETE_CONTENT)],
            allow_missing=False,
        )

    assert "Incomplete report submission is not allowed" in pipeline.agent_failures["chatgpt"]
