"""V2.0 多智能体 AI 基金经理系统 单元测试。"""

import pytest

from graph.state import FundState
from graph.fund_graph import build_graph
from agents.research_agent import ResearchAgent
from agents.quant_agent import QuantAgentV20
from agents.macro_agent import MacroAgentV20
from agents.trader_agent import TraderAgent
from agents.risk_agent import RiskAgent
from agents.cio_agent import CIOAgent
from memory.investment_memory import InvestmentMemory
from reports.report_generator import ReportGenerator


class TestFundState:
    def test_typed_dict(self):
        s: FundState = {
            "stock_code": "300394",
            "research_report": "优秀成长公司",
            "quant_signal": "BUY",
            "trader_signal": "OPEN_POSITION",
            "risk_result": "Risk OK",
            "macro_view": "中性",
            "final_decision": "BUY",
            "confidence": 0.8,
        }
        assert s["stock_code"] == "300394"
        assert s["confidence"] == 0.8


class TestResearchAgent:
    def test_analyze_contains_stock(self):
        report = ResearchAgent().analyze("600519")
        assert "600519" in report
        assert "基本面分析" in report


class TestQuantAgent:
    def test_buy_when_score_high(self):
        qa = QuantAgentV20()
        assert qa.analyze({"momentum": 0.05, "volume": 2.0, "trend": "UP"}) == "BUY"

    def test_sell_when_score_low(self):
        qa = QuantAgentV20()
        assert qa.analyze({"momentum": -0.05, "volume": 1.0, "trend": "DOWN"}) == "SELL"

    def test_hold_middle(self):
        qa = QuantAgentV20()
        # momentum>0(+40) + 无其他加分 = 40，介于 30~70 → HOLD
        assert qa.analyze({"momentum": 0.05, "volume": 1.0, "trend": "FLAT"}) == "HOLD"


class TestMacroAgent:
    def test_analyze(self):
        out = MacroAgentV20().analyze()
        assert out["market"] == "NEUTRAL"
        assert out["risk"] == "MEDIUM"


class TestTraderAgent:
    def test_buy(self):
        assert TraderAgent().execute("BUY") == {"action": "OPEN_POSITION", "position": 0.2}

    def test_sell(self):
        assert TraderAgent().execute("SELL") == {"action": "CLOSE_POSITION"}

    def test_wait(self):
        assert TraderAgent().execute("HOLD") == {"action": "WAIT"}


class TestRiskAgent:
    def test_reject_over_position(self):
        out = RiskAgent().check("300394", 0.5)
        assert out["approved"] is False
        assert "仓位" in out["reason"]

    def test_approve(self):
        out = RiskAgent().check("300394", 0.1)
        assert out["approved"] is True


class TestCIOAgent:
    def test_buy_when_two_votes(self):
        state = {"quant_signal": "BUY", "research_report": "优秀成长公司"}
        assert CIOAgent().decide(state) == "BUY"

    def test_hold_otherwise(self):
        state = {"quant_signal": "SELL", "research_report": "一般"}
        assert CIOAgent().decide(state) == "HOLD"


class TestInvestmentMemory:
    def test_save_recall_last10(self):
        mem = InvestmentMemory()
        for i in range(15):
            mem.save(f"event{i}")
        assert mem.recall() == [f"event{i}" for i in range(5, 15)]


class TestReportGenerator:
    def test_generate_contains_morning_report(self):
        state = {
            "stock_code": "300394",
            "research_report": "优秀成长公司",
            "quant_signal": "BUY",
            "macro_view": "中性",
            "final_decision": "BUY",
        }
        text = ReportGenerator().generate(state)
        assert "AI基金晨报" in text
        assert "300394" in text
        assert "BUY" in text


class TestFundGraph:
    def test_build_graph_compiles(self):
        graph = build_graph()
        assert graph is not None
