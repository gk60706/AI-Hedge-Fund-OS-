"""V2.9 AI 多 Agent 投资委员会（AI Multi-Agent Investment Committee）单元测试。"""

import pytest

from agents.base_agent import BaseAgent
from agents.value_agent import ValueAgentV29
from agents.trend_agent import TrendAgentV29
from agents.quant_agent import QuantAgentV29
from agents.macro_agent import MacroAgentV29
from agents.risk_agent import RiskAgentV29
from agents.research_agent import ResearchAgentV29
from agents.investment_committee import InvestmentCommitteeV29
from committee.voting import CommitteeVoting
from committee.allocator import PositionAllocator
from committee.decision import InvestmentDecision


class TestBaseAgent:
    def test_abstract(self):
        with pytest.raises(TypeError):
            BaseAgent()

    def test_normalize_score(self):
        class Dummy(BaseAgent):
            def analyze(self, context):
                return {}

        d = Dummy()
        assert d.normalize_score(-5) == 0.0
        assert d.normalize_score(50) == 50.0
        assert d.normalize_score(150) == 100.0


class TestValueAgentV29:
    def test_pe_low(self):
        a = ValueAgentV29()
        r = a.analyze({"market_data": {"pe_dynamic": 10, "pb": 2.0}})
        assert r["score"] == 75.0
        assert r["signal"] == "BUY"

    def test_pe_high(self):
        a = ValueAgentV29()
        r = a.analyze({"market_data": {"pe_dynamic": 80, "pb": 10.0}})
        assert r["score"] == 25.0
        assert r["signal"] == "SELL"

    def test_default(self):
        a = ValueAgentV29()
        r = a.analyze({})
        assert r["score"] == 50.0
        assert r["signal"] == "HOLD"
        assert r["agent"] == "value_agent"


class TestTrendAgentV29:
    def test_strong_up(self):
        a = TrendAgentV29()
        r = a.analyze({"market_data": {"change_pct": 5.0}})
        assert r["score"] == 70.0
        assert r["signal"] == "BUY"

    def test_strong_down(self):
        a = TrendAgentV29()
        r = a.analyze({"market_data": {"change_pct": -5.0}})
        assert r["score"] == 30.0
        assert r["signal"] == "SELL"


class TestQuantAgentV29:
    def test_score(self):
        a = QuantAgentV29()
        r = a.analyze({"quant_signal": {"score": 80, "reasons": ["x"]}})
        assert r["score"] == 80.0
        assert r["signal"] == "BUY"
        assert r["reasons"] == ["x"]


class TestMacroAgentV29:
    def test_regime(self):
        a = MacroAgentV29()
        r = a.analyze({"macro": {"score": 30, "regime": "BEAR"}})
        assert r["regime"] == "BEAR"
        assert r["signal"] == "SELL"


class TestRiskAgentV29:
    def test_low_risk(self):
        a = RiskAgentV29()
        r = a.analyze({"risk": {"max_drawdown": -0.05, "volatility": 0.02}})
        assert r["signal"] == "LOW_RISK"

    def test_high_risk(self):
        a = RiskAgentV29()
        r = a.analyze({"risk": {"max_drawdown": -0.40, "volatility": 0.10}})
        assert r["signal"] == "HIGH_RISK"
        assert r["score"] == 40.0


class TestResearchAgentV29:
    def test_average(self):
        a = ResearchAgentV29()
        r = a.analyze({"agent_results": {"x": {"score": 60}, "y": {"score": 80}}})
        assert r["score"] == 70.0
        assert r["agents_used"] == 2
        assert r["signal"] == "BUY"


class TestCommitteeVoting:
    def test_buy(self):
        v = CommitteeVoting()
        r = v.vote({
            "value_agent": {"signal": "BUY"},
            "trend_agent": {"signal": "BUY"},
            "quant_agent": {"signal": "BUY"},
            "macro_agent": {"signal": "HOLD"},
            "risk_agent": {"signal": "LOW_RISK"},
        })
        assert r["decision"] == "BUY"
        assert r["weighted_score"] == 3.5

    def test_hold(self):
        v = CommitteeVoting()
        r = v.vote({
            "value_agent": {"signal": "HOLD"},
            "trend_agent": {"signal": "HOLD"},
            "quant_agent": {"signal": "BUY"},
            "macro_agent": {"signal": "HOLD"},
            "risk_agent": {"signal": "LOW_RISK"},
        })
        assert r["decision"] == "HOLD"
        assert r["weighted_score"] == 1.5

    def test_weights(self):
        v = CommitteeVoting()
        r = v.vote({
            "quant_agent": {"signal": "BUY"},
            "risk_agent": {"signal": "SELL"},
        })
        assert r["votes"]["quant_agent"]["weight"] == 1.5
        assert r["votes"]["risk_agent"]["weight"] == 1.5


class TestInvestmentCommitteeV29:
    def test_deliberate(self):
        c = InvestmentCommitteeV29()
        context = {
            "market_data": {"pe_dynamic": 35, "pb": 5.2, "change_pct": 2.35},
            "quant_signal": {"score": 78},
            "macro": {"score": 65, "regime": "NEUTRAL_BULLISH"},
            "risk": {"max_drawdown": -0.12, "volatility": 0.028},
        }
        r = c.deliberate(context)
        assert set(r["agents"].keys()) == {
            "value_agent", "trend_agent", "quant_agent", "macro_agent", "risk_agent",
        }
        assert "decision" in r["committee"]
        assert "weighted_score" in r["committee"]


class TestPositionAllocator:
    def test_sell_zero(self):
        a = PositionAllocator()
        r = a.allocate("SELL", 90, 1_000_000)
        assert r == {"position_ratio": 0.0, "position_value": 0.0}

    def test_hold_zero(self):
        a = PositionAllocator()
        r = a.allocate("HOLD", 90, 1_000_000)
        assert r == {"position_ratio": 0.0, "position_value": 0.0}

    def test_buy(self):
        a = PositionAllocator()
        r = a.allocate("BUY", 80, 1_000_000)
        assert r["position_ratio"] == 0.16
        assert r["position_value"] == 160000.0


class TestInvestmentDecision:
    def test_build(self):
        d = InvestmentDecision()
        committee_result = {
            "committee": {"decision": "BUY", "weighted_score": 3.0, "votes": {"x": 1}},
            "agents": {"value_agent": {"score": 70}},
        }
        allocation = {"position_ratio": 0.16, "position_value": 160000.0}
        r = d.build("300394", committee_result, allocation)
        assert r["code"] == "300394"
        assert r["decision"] == "BUY"
        assert r["position_ratio"] == 0.16
        assert r["agent_analysis"]["value_agent"]["score"] == 70


class TestMainV29:
    def test_main(self, capsys):
        import main_v29
        main_v29.main()
        out = capsys.readouterr().out
        assert "AI HEDGE FUND OS V2.9" in out
        assert "投资委员会决策:" in out
