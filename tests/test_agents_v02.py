"""V0.2 多 Agent 模块测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from agents.common import _client
from agents.decision_agent import decision_agent
from agents.models import AgentResult, InvestmentDecision
from agents.quant_agent import quant_agent
from agents.research_agent import research_agent
from agents.risk_agent import risk_agent
from agents.workflow import build_agent_graph, run_agent_research


# ---------------------------------------------------------------- models

def test_agent_result_model():
    r = AgentResult(agent="X", score=80, opinion="ok", risks=["a"])
    assert r.score == 80
    assert r.risks == ["a"]


def test_investment_decision_model():
    d = InvestmentDecision(stock="300394", score=80, action="BUY", position=0.2, reason="x")
    assert d.action == "BUY"


# ---------------------------------------------------------------- agents

def test_research_agent_normal():
    r = research_agent({"turnover": 8})
    assert r.agent == "Research"
    assert r.score == 60
    assert r.risks == []


def test_research_agent_high_turnover():
    r = research_agent({"turnover": 20})
    assert r.score == 50
    assert "换手率过高" in r.risks


def test_quant_agent_above_ma20():
    history = pd.DataFrame({"收盘": [10.0] * 19 + [12.0]})
    r = quant_agent(history)
    assert r.score == 70
    assert r.opinion == "价格站上20日均线"


def test_quant_agent_below_ma20():
    history = pd.DataFrame({"收盘": [12.0] * 19 + [10.0]})
    r = quant_agent(history)
    assert r.score == 30
    assert "趋势偏弱" in r.risks


def test_quant_agent_empty_history():
    r = quant_agent(pd.DataFrame(columns=["收盘"]))
    assert r.score == 50


def test_risk_agent_normal():
    r = risk_agent({"change": 3})
    assert r.score == 70


def test_risk_agent_hot():
    r = risk_agent({"change": 10})
    assert r.score == 50
    assert "短期涨幅过大" in r.risks


def test_decision_agent_buy():
    results = [AgentResult(agent="a", score=90, opinion="", risks=[]),
               AgentResult(agent="b", score=80, opinion="", risks=[])]
    d = decision_agent({"code": "300394"}, results)
    assert d.action == "BUY"
    assert d.position == 0.2


def test_decision_agent_hold():
    results = [AgentResult(agent="a", score=60, opinion="", risks=[]),
               AgentResult(agent="b", score=50, opinion="", risks=[])]
    d = decision_agent({"code": "300394"}, results)
    assert d.action == "HOLD"
    assert d.position == 0.1


def test_decision_agent_avoid():
    results = [AgentResult(agent="a", score=40, opinion="", risks=[]),
               AgentResult(agent="b", score=30, opinion="", risks=[])]
    d = decision_agent({"code": "300394"}, results)
    assert d.action == "AVOID"
    assert d.position == 0


def test_decision_agent_requires_results():
    with pytest.raises(ValueError):
        decision_agent({"code": "300394"}, [])


# ---------------------------------------------------------------- common

def test_common_client_requires_key(monkeypatch):
    import agents.common as common
    monkeypatch.setattr(common.settings, "openai_api_key", "")
    with pytest.raises(RuntimeError):
        _client()


# ---------------------------------------------------------------- workflow V0.2

def test_build_agent_graph_compiles():
    graph = build_agent_graph()
    assert graph is not None


def test_run_agent_research_full_flow(monkeypatch):
    monkeypatch.setattr(
        "agents.workflow.get_stock_price",
        lambda code: {
            "code": code, "name": "天孚通信", "price": 267.0,
            "change": 7.36, "volume": 519294.0, "amount": 1.36e10,
            "turnover": 4.77,
        },
    )
    monkeypatch.setattr(
        "agents.workflow.get_history",
        lambda code: pd.DataFrame({"收盘": [250.0, 255.0, 260.0]}),
    )
    result = run_agent_research("300394")
    assert result["stock"]["code"] == "300394"
    assert len(result["results"]) == 3
    assert result["decision"].stock == "300394"
    assert result["decision"].action in ("BUY", "HOLD", "AVOID")


def test_run_agent_research_invalid_code():
    with pytest.raises(ValueError):
        run_agent_research("abc")
