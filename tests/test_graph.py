"""LangGraph 研究流程测试（模拟数据 + 模拟 LLM）。"""
from __future__ import annotations

import pandas as pd
import pytest

from app.ai.graph import build_research_graph


class FakeOpenAIClient:
    """模拟 OpenAI Responses API 客户端。"""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        pass

    def complete(self, *, prompt: str, system: str | None = None, temperature: float = 0.3) -> str:
        assert "000001" in prompt
        assert "行情数据摘要" in prompt
        return "# 测试报告\n\n行情概览：数据已获取。"


def test_graph_full_flow(monkeypatch, fake_daily_df, fake_company_info_df):
    """正常路径：取数 -> 生成报告。"""
    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_hist", lambda **kwargs: fake_daily_df)
    monkeypatch.setattr(
        "app.market.provider.ak.stock_individual_info_em",
        lambda **kwargs: fake_company_info_df,
    )
    monkeypatch.setattr("app.ai.nodes.OpenAIClient", FakeOpenAIClient)

    graph = build_research_graph()
    result = graph.invoke({"symbol": "000001", "focus": "估值"})

    assert "# 测试报告" in result["report"]
    assert len(result["market_rows"]) == 2
    assert result["company_info"]["股票简称"] == "平安银行"
    assert "error" not in result or result.get("error") is None


def test_graph_data_failure_still_generates(monkeypatch, fake_company_info_df):
    """行情获取失败时不阻断，仍生成报告并附带说明。"""

    def _boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_hist", _boom)
    monkeypatch.setattr(
        "app.market.provider.ak.stock_individual_info_em",
        lambda **kwargs: fake_company_info_df,
    )

    class FakeOpenAIClientWithNote(FakeOpenAIClient):
        def complete(self, *, prompt, system=None, temperature=0.3):
            return "仍然生成了报告。"

    monkeypatch.setattr("app.ai.nodes.OpenAIClient", FakeOpenAIClientWithNote)

    graph = build_research_graph()
    result = graph.invoke({"symbol": "000001"})
    assert "注意" in result["report"]
    assert "network down" in result["report"]
    assert result.get("error")


def test_openai_client_requires_key(monkeypatch):
    """未配置 OPENAI_API_KEY 时 OpenAIClient 必须报错。"""
    from app.ai.client import OpenAIClient

    monkeypatch.setattr(
        "app.ai.client.get_settings",
        lambda: type("S", (), {"openai_api_key": "", "openai_model": "gpt-4o-mini"})(),
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIClient()
