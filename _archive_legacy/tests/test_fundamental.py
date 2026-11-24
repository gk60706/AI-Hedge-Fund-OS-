"""V0.4 基本面模块测试。"""
from __future__ import annotations

from fundamental.financial_agent import financial_agent
from fundamental.fundamental_engine import run_fundamental_analysis
from fundamental.industry_agent import industry_agent
from fundamental.moat_agent import moat_agent
from fundamental.news_agent import news_agent
from fundamental.pdf_agent import read_pdf, summarize_report
from fundamental.valuation_agent import valuation_agent
from pipeline.fundamental_pipeline import run_ai_selection
from reports.report_generator import generate_report


def test_financial_agent_good():
    r = financial_agent({"roe": 20, "gross_margin": 40})
    assert r.score == 85
    assert r.risks == []


def test_financial_agent_poor():
    r = financial_agent({"roe": 3, "gross_margin": 5})
    assert r.score <= 50
    assert "ROE偏低" in r.risks


def test_news_agent_positive():
    r = news_agent("订单增长 重大突破")
    assert r.score == 65


def test_news_agent_negative():
    r = news_agent("公司遭处罚 股东减持")
    assert r.score <= 50
    assert "处罚" in r.risks


def test_industry_agent_hot():
    r = industry_agent("AI 半导体 新能源 机器人")
    assert r.score == 90


def test_moat_agent():
    r = moat_agent("行业龙头 拥有多项专利")
    assert r.score == 70


def test_valuation_agent():
    assert valuation_agent({"pe": 20}).score == 70
    assert valuation_agent({"pe": 100}).score == 30
    assert valuation_agent({}).score == 50


def test_fundamental_engine():
    result = run_fundamental_analysis(
        financial={"roe": 20, "gross_margin": 35, "pe": 25},
        news="订单增长 合作突破",
        industry="AI 半导体",
        company="行业龙头",
    )
    assert len(result["agents"]) == 5
    assert 0 <= result["fundamental_score"] <= 100


def test_report_generator():
    result = run_fundamental_analysis(
        financial={}, news="", industry="AI", company="测试公司"
    )
    text = generate_report("300394", result)
    assert "# AI Hedge Fund OS 投资研究报告" in text
    assert "300394" in text
    assert "基本面评分" in text


def test_pdf_agent_summarize():
    summary = summarize_report("公司订单增长，利润提升，布局人工智能研发")
    assert summary["length"] > 0
    assert "人工智能" in summary["keywords"]
    assert "订单" in summary["keywords"]


def test_pipeline_ai_selection(monkeypatch):
    monkeypatch.setattr(
        "pipeline.fundamental_pipeline.scan_market",
        lambda top_n: [
            {"code": "300394", "name": "天孚通信", "fund_score": 90},
            {"code": "000001", "name": "平安银行", "fund_score": 60},
        ],
    )
    result = run_ai_selection()
    assert len(result) == 2
    assert all("fundamental_score" in s for s in result)
    # 排序：天孚通信应在前
    assert result[0]["name"] == "天孚通信" or result[0]["fundamental_score"] >= result[1]["fundamental_score"]
