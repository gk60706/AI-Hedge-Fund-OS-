from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from tools.market_tool import MarketDataError


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "service": "ai-hedge-fund-os",
        "version": "0.4.0",
    }


def test_market_endpoint_success(monkeypatch):
    monkeypatch.setattr(
        "backend.main.get_a_share_quote",
        lambda code: {"code": code, "name": "天孚通信", "latest_price": 88.5},
    )
    client = TestClient(app)
    resp = client.get("/api/v1/market/300394")
    assert resp.status_code == 200
    assert resp.json()["code"] == "300394"
    assert resp.json()["name"] == "天孚通信"


def test_market_endpoint_error(monkeypatch):
    def boom(code: str):
        raise MarketDataError("AkShare 数据源不可用")

    monkeypatch.setattr("backend.main.get_a_share_quote", boom)
    client = TestClient(app)
    resp = client.get("/api/v1/market/300394")
    assert resp.status_code == 502
    assert "AkShare" in resp.json()["detail"]


def test_research_endpoint_success(monkeypatch):
    monkeypatch.setattr(
        "backend.main.run_research",
        lambda code: {
            "code": code,
            "report": "## 分析结论\n测试报告",
            "report_path": "reports/300394_test.md",
        },
    )
    client = TestClient(app)
    resp = client.get("/api/v1/research/300394")
    assert resp.status_code == 200
    assert resp.json()["report_path"].startswith("reports/")


def test_research_endpoint_error(monkeypatch):
    def boom(code: str):
        raise RuntimeError("OPENAI_API_KEY 未配置")

    monkeypatch.setattr("backend.main.run_research", boom)
    client = TestClient(app)
    resp = client.get("/api/v1/research/300394")
    assert resp.status_code == 502
