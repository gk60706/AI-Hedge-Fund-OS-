"""API 集成测试（TestClient + mock 数据源，不触网、不调用真实 LLM）。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


def test_market_history_endpoint(monkeypatch, fake_daily_df):
    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_hist", lambda **kwargs: fake_daily_df)
    client = TestClient(create_app())

    resp = client.get("/api/v1/market/history", params={"symbol": "000001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "000001"
    assert data["total"] == 2
    assert data["bars"][0]["close"] == 10.2


def test_market_history_invalid_symbol():
    client = TestClient(create_app())
    resp = client.get("/api/v1/market/history", params={"symbol": "ABC"})
    assert resp.status_code == 422


def test_research_analyze_endpoint(
    monkeypatch,
    fake_daily_df,
    fake_company_info_df,
    isolated_reports,
):
    """端到端：POST /api/v1/research/analyze 返回报告并落盘。"""

    class FakeOpenAIClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def complete(self, *, prompt: str, system: str | None = None, temperature: float = 0.3) -> str:
            return "# 报告\n\nAPI 集成测试内容。"

    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_hist", lambda **kwargs: fake_daily_df)
    monkeypatch.setattr(
        "app.market.provider.ak.stock_individual_info_em",
        lambda **kwargs: fake_company_info_df,
    )
    monkeypatch.setattr("app.ai.nodes.OpenAIClient", FakeOpenAIClient)

    client = TestClient(create_app())
    resp = client.post("/api/v1/research/analyze", json={"symbol": "000001", "focus": "综合"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_id"]
    assert "API 集成测试内容" in body["report"]

    # 报告应已写入隔离目录
    saved = isolated_reports.dir / f"{body['report_id']}.md"
    assert saved.exists()
    assert "API 集成测试内容" in saved.read_text(encoding="utf-8")

    # 列表与读取接口可用
    list_resp = client.get("/api/v1/reports")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    get_resp = client.get(f"/api/v1/reports/{body['report_id']}")
    assert get_resp.status_code == 200
    assert "API 集成测试内容" in get_resp.json()["content"]

    missing = client.get("/api/v1/reports/not_exist_id")
    assert missing.status_code == 404
