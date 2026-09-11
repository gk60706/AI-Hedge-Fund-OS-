"""V2.1 财报 + 新闻 + MCP 工具生态（Research Intelligence Layer）单元测试。"""

import os
import tempfile

import pytest

from mcp.server import MCPServer
from mcp.tools import MarketTool, NewsTool, FinancialTools
from mcp.register import server
from research.pdf_agent import PDFResearchAgent
from research.news_agent import NewsAgent
from research.financial_agent import FinancialAgent
from memory.vector_memory import VectorMemory
from rag.document_loader import DocumentLoader, load_pdf
from reports.ai_research_report import ResearchReportGenerator
from agents.cio_v21 import CIOAgentV21


class TestMCPServerV21:
    def test_register_and_call(self):
        s = MCPServer()
        t = FinancialTools()
        s.register("company_info", t.company_info)
        out = s.call("company_info", {"code": "300394"})
        assert out["code"] == "300394"
        assert out["industry"] == "AI产业链"

    def test_tool_not_found(self):
        s = MCPServer()
        with pytest.raises(Exception):
            s.call("not_exist", {})

    def test_old_v11_path_kept(self):
        # V1.1 老接口：call(tool, {"method": value}) 必须仍然可用
        s = MCPServer()
        out = s.call("market", {"get_price": "600519"})
        assert out["price"] == 120
        news = s.call("news", {"search": "AI"})
        assert "AI产业增长" in news


class TestFinancialTools:
    def test_company_info(self):
        t = FinancialTools()
        out = t.company_info("688568")
        assert out["code"] == "688568"
        assert out["status"] == "成长"

    def test_news_search(self):
        t = FinancialTools()
        out = t.news_search("AI")
        assert out[0]["title"] == "AI 最新行业动态"
        assert out[0]["sentiment"] == "positive"


class TestRegisterServer:
    def test_default_server_has_tools(self):
        out = server.call("company_info", {"code": "300394"})
        assert out["industry"] == "AI产业链"


class TestPDFResearchAgent:
    def test_summarize(self):
        agent = PDFResearchAgent()
        out = agent.summarize("财报文本")
        assert "business" in out
        assert "growth" in out
        assert "risk" in out


class TestNewsAgent:
    def test_positive_news(self):
        agent = NewsAgent()
        out = agent.analyze([{"sentiment": "positive"}, {"sentiment": "negative"}])
        # positive/(positive+negative+1) = 1/3
        assert out["sentiment_score"] == pytest.approx(1 / 3)


class TestFinancialAgent:
    def test_quote(self):
        out = FinancialAgent().quote("300394")
        assert out["code"] == "300394"

    def test_fundamentals(self):
        out = FinancialAgent().fundamentals("300394")
        assert out["code"] == "300394"


class TestVectorMemory:
    def test_save_and_search(self):
        vm = VectorMemory()
        vm.save("贵州茅台 2025 年报 收入增长", "note-1")
        result = vm.search("贵州茅台")
        assert result is not None


class TestDocumentLoader:
    def test_load_folder(self, tmp_path):
        (tmp_path / "a.txt").write_text("文档A内容", encoding="utf-8")
        (tmp_path / "b.txt").write_text("文档B内容", encoding="utf-8")
        (tmp_path / "c.log").write_text("忽略我", encoding="utf-8")
        loader = DocumentLoader()
        docs = loader.load_folder(str(tmp_path))
        assert len(docs) == 2
        assert "文档A内容" in docs


class TestResearchReportGenerator:
    def test_generate(self):
        gen = ResearchReportGenerator()
        out = gen.generate("AI产业链公司", "收入增长20%", "舆情正面")
        assert "# AI投资研究报告" in out
        assert "AI产业链公司" in out
        assert "BUY / HOLD / SELL" in out


class TestCIOAgentV21:
    def test_research(self):
        cio = CIOAgentV21()
        result = cio.research("300394", server)
        assert result["company"]["industry"] == "AI产业链"
        assert len(result["news"]) > 0

    def test_decide(self):
        cio = CIOAgentV21()
        assert cio.decide({"news": [1]}) == "BUY_WATCH"
        assert cio.decide({"news": []}) == "HOLD"
