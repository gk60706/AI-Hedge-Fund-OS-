from __future__ import annotations

from pathlib import Path

import pytest

from agents.workflow import build_graph, run_research


def test_build_graph_compiles():
    graph = build_graph()
    assert graph is not None


def test_run_research_invalid_code():
    with pytest.raises(ValueError):
        run_research("123")
    with pytest.raises(ValueError):
        run_research("abc")


def test_run_research_full_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "agents.workflow.get_a_share_quote",
        lambda code: {"code": code, "name": "天孚通信", "latest_price": 88.5},
    )
    monkeypatch.setattr(
        "agents.workflow.generate_cio_report",
        lambda data: "## 分析结论\n测试报告内容",
    )
    monkeypatch.setattr("agents.workflow.REPORT_DIR", tmp_path)

    result = run_research("sh300394")

    assert result["code"] == "300394"
    assert result["market_data"]["name"] == "天孚通信"
    assert result["report"] == "## 分析结论\n测试报告内容"
    assert result["report_path"]
    report_file = Path(result["report_path"])
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "股票代码" in content
    assert "CIO 分析" in content
