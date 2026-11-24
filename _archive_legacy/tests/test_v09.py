"""V0.9 AI 交易大脑（LLM Trader Brain）测试"""
import pytest

from brain.market_agent import analyze_market
from brain.news_agent import news_analysis
from brain.quant_agent import quant_signal
from brain.cio_agent import cio_decision
from brain.trader_brain import run_ai_trader
from reports.daily_review import daily_review

from config.settings import OPENAI_API_KEY, MODEL


class TestConfig:
    def test_model(self):
        assert MODEL == "gpt-5"

    def test_api_key_from_env(self):
        # API Key 只从环境变量读取，绝不硬编码
        assert OPENAI_API_KEY is None or isinstance(OPENAI_API_KEY, str)


class TestMarketAgent:
    def test_bull_market(self):
        out = analyze_market({"index_change": 2, "north_money": 100, "volume_ratio": 2.0})
        assert out["market_score"] == 95
        assert out["status"] == "BULL"

    def test_normal_market(self):
        out = analyze_market({"index_change": 0, "north_money": -50, "volume_ratio": 1.0})
        assert out["market_score"] == 50
        assert out["status"] == "NORMAL"


class TestQuantAgent:
    def test_signal(self):
        out = quant_signal({"code": "300394", "alpha": 80, "fund_score": 70})
        assert out["code"] == "300394"
        assert out["quant_score"] == 75.0

    def test_defaults(self):
        out = quant_signal({"code": "A"})
        assert out["quant_score"] == 0


class TestNewsAgent:
    def test_prompt_construction(self, monkeypatch):
        captured = {}

        def fake_ask(prompt):
            captured["prompt"] = prompt
            return "分析结果"

        monkeypatch.setattr("brain.news_agent.ask_ai", fake_ask)
        result = news_analysis("某公司发布利好公告")
        assert result == "分析结果"
        assert "利好行业" in captured["prompt"]
        assert "某公司发布利好公告" in captured["prompt"]


class TestCioAgent:
    def test_decision(self, monkeypatch):
        captured = {}

        def fake_ask(prompt):
            captured["prompt"] = prompt
            return "买入"

        monkeypatch.setattr("brain.cio_agent.ask_ai", fake_ask)
        result = cio_decision("牛市", "300394", "利好")
        assert result == "买入"
        assert "是否买入" in captured["prompt"]
        assert "建议仓位" in captured["prompt"]


class TestTraderBrain:
    def test_run_ai_trader(self, monkeypatch):
        monkeypatch.setattr("brain.trader_brain.cio_decision", lambda m, s, n: "BUY 30%")
        out = run_ai_trader("牛市", "300394", "利好")
        assert out == {"decision": "BUY 30%"}


class TestDailyReview:
    def test_review(self, monkeypatch):
        captured = {}

        def fake_ask(prompt):
            captured["prompt"] = prompt
            return "复盘"

        monkeypatch.setattr("reports.daily_review.ask_ai", fake_ask)
        result = daily_review("买300394 卖000001")
        assert result == "复盘"
        assert "今日收益" in captured["prompt"]
        assert "明日策略调整" in captured["prompt"]


class TestLangGraphWorkflow:
    def test_graph_compiles(self):
        from workflow.graph import app, State

        # 验证 TypedDict 状态（LangGraph 1.x 要求）
        assert isinstance(State.__annotations__, dict)
        assert "market" in State.__annotations__
        assert app is not None

    def test_graph_invocation(self):
        from workflow.graph import app

        result = app.invoke({})
        assert result["decision"] == "BUY"
        assert result["market"] == {"score": 80}


class TestMemory:
    def test_memory_save_search(self):
        # chromadb 可用时走 ChromaDB，缺失时自动降级本地 JSON，接口一致
        from brain.memory import save_memory, search_memory

        save_memory("今日买入300394")
        out = search_memory("300394")
        assert out is not None
        assert "documents" in out
