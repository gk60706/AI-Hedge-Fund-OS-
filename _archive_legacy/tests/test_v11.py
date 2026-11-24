"""V1.1 自主投资 Agent 升级版测试：LangGraph / MCP / RAG / 策略实验室。"""
import pytest

from agent_core.state import FundState
from agent_core.graph import app
from mcp.tools import MarketTool, NewsTool
from mcp.server import MCPServer
from rag.document_loader import load_pdf
from strategy_lab.evaluator import evaluate
from strategy_lab.evolution import evolve


def test_fund_state_keys():
    state: FundState = {
        "stock": {},
        "market": {},
        "research": [],
        "risk": {},
        "strategy": {},
        "decision": "",
        "memory": [],
    }
    assert set(state.keys()) == {
        "stock", "market", "research", "risk", "strategy", "decision", "memory"
    }


def test_langgraph_workflow_research_quant_risk_decision():
    result = app.invoke(
        {
            "stock": {"code": "300394"},
            "market": {"trend": "BULL"},
            "research": [],
            "risk": {},
            "strategy": {},
            "decision": "",
            "memory": [],
        }
    )
    assert [x["agent"] for x in result["research"]] == ["Research", "Quant"]
    assert result["risk"] == {"risk": "LOW"}
    assert result["decision"] == "BUY"


def test_mcp_server_dispatch():
    server = MCPServer()
    assert server.call("market", {"get_price": "300394"})["price"] == 120
    assert "AI产业增长" in server.call("news", {"search": "AI"})
    assert MarketTool().name == "market"
    assert NewsTool().name == "news"


def test_pdf_loader_importable():
    # 不依赖真实 PDF 文件，仅验证函数可调用签名
    assert callable(load_pdf)


def test_chromadb_vector_store():
    # chromadb 可用时走 ChromaDB，缺失时自动降级本地 JSON，接口一致
    import rag.vector_store as vs
    vs.add_document("AI产业增长")
    result = vs.search("AI产业")
    assert result is not None
    assert "documents" in result


def test_strategy_evaluator_keep_and_drop():
    assert evaluate({"return": 0.25, "drawdown": 0.1, "sharpe": 1.5})["status"] == "KEEP"
    assert evaluate({"return": 0.05, "drawdown": 0.3, "sharpe": 0.5})["status"] == "DROP"


def test_strategy_evolution_filters_low_scores():
    alive = evolve([{"score": 90}, {"score": 50}, {"score": 85}])
    assert len(alive) == 2


def test_strategy_generator_uses_responses_api():
    # 仅验证 import 与客户端构造（OpenAI 余额为 0，不发起真实调用）
    from strategy_lab import generator
    assert callable(generator.create_strategy)
    from core.config import get_openai_client, get_openai_model
    assert get_openai_model()  # 默认 gpt-5 或 .env 覆盖
    client = get_openai_client()
    assert client is not None


def test_main_v11_runs():
    # main_v11.py 顶层即演示流程，import 即执行，验证无异常
    import main_v11  # noqa: F401
