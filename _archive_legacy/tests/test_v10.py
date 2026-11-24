"""V1.0 MVP 正式版测试：委员会多 Agent 流程与工具层。"""
import pytest

from core.agent import BaseAgent
from agents.fundamental_agent import FundamentalAgent
from agents.quant_agent import QuantAgent
from agents.news_agent import NewsAgent
from committee.research_committee import ResearchCommittee
from committee.cio import CIOAgent
from committee.risk_committee import RiskCommittee
from mcp.market_tool import MarketTool
from mcp.report_tool import ReportTool
from portfolio.manager import PortfolioManager
from reports.morning_report import morning_report
from reports.evening_report import evening_report


def test_base_agent_is_abstract():
    with pytest.raises(TypeError):
        BaseAgent("x")


def test_fundamental_agent_scores_roe_and_growth():
    agent = FundamentalAgent("基本面分析师")
    r = agent.run({"roe": 20, "growth": 30})
    assert r["agent"] == "基本面分析师"
    assert r["score"] == 95
    assert r["reason"] == "盈利能力分析"


def test_quant_agent_uses_alpha():
    agent = QuantAgent("量化分析师")
    assert agent.run({"alpha": 85})["score"] == 85


def test_news_agent_positive_keywords():
    agent = NewsAgent("新闻分析师")
    assert agent.run({"news": "AI订单增长 合作"})["score"] == 80
    assert agent.run({"news": "无实质消息"})["score"] == 50


def test_research_committee_average_score():
    committee = ResearchCommittee(
        [FundamentalAgent("基本面"), QuantAgent("量化"), NewsAgent("新闻")]
    )
    result = committee.analyze({"roe": 20, "growth": 30, "alpha": 85, "news": "AI订单增长"})
    assert result["research_score"] == pytest.approx(83.333, abs=0.01)
    assert len(result["detail"]) == 3


def test_cio_decide_buy_watch_pass():
    cio = CIOAgent()
    assert cio.decide({"research_score": 85})["decision"] == "BUY"
    assert cio.decide({"research_score": 70})["decision"] == "WATCH"
    assert cio.decide({"research_score": 40})["decision"] == "PASS"
    assert cio.decide({"research_score": 40})["position"] == 0


def test_risk_committee_red_when_volatile():
    rc = RiskCommittee()
    assert rc.check([{"volatility": 0.35}])["status"] == "RED"
    assert rc.check([{"volatility": 0.1}])["status"] == "NORMAL"


def test_portfolio_manager_allocates_buy_only():
    pm = PortfolioManager()
    portfolio = pm.allocate(
        [
            {"code": "300394", "decision": "BUY", "position": 0.2},
            {"code": "600519", "decision": "WATCH", "position": 0.05},
        ]
    )
    assert len(portfolio) == 1
    assert portfolio[0] == {"code": "300394", "weight": 0.2}


def test_mcp_tools():
    assert MarketTool().get_price("300394")["code"] == "300394"
    assert "AI基金报告" in ReportTool().generate("测试数据")


def test_morning_and_evening_reports():
    assert "AI基金晨报" in morning_report("BULL", "300394")
    assert "AI交易复盘" in evening_report("buy 300394")


def test_main_v10_runs():
    # main.py 顶层即演示流程，import 即执行，验证无异常
    import main  # noqa: F401
