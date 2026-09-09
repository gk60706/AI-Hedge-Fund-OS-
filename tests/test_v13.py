"""V1.3 策略竞技场 + 多 Agent 基金委员会测试"""
import pytest

from agents.base_manager import InvestmentManager
from agents.value_agent import ValueAgent
from agents.trend_agent import TrendAgent
from agents.quant_agent import QuantAgent
from agents.macro_agent import MacroAgent

from arena.battle import StrategyArena
from arena.ranking import StrategyRanking
from arena.champion import ChampionStrategy

from committee.voting import VotingSystem
from committee.investment_committee import InvestmentCommittee
from committee.risk_agent import RiskAgent

from allocation.capital_allocator import CapitalAllocator

from genome.champion_db import ChampionDB

from fund.team import create_team


class TestBaseManager:
    def test_not_implemented(self):
        with pytest.raises(NotImplementedError):
            InvestmentManager("x").analyze({})


class TestValueAgent:
    def test_low_pe_high_roe(self):
        out = ValueAgent("v").analyze({"pe": 20, "roe": 20})
        assert out["style"] == "VALUE"
        assert out["score"] == 90

    def test_default(self):
        assert ValueAgent("v").analyze({})["score"] == 50


class TestTrendAgent:
    def test_momentum_volume(self):
        out = TrendAgent("t").analyze({"momentum": 1, "volume": 2})
        assert out["style"] == "TREND"
        assert out["score"] == 100


class TestQuantAgentV13:
    def test_analyze(self):
        out = QuantAgent("q").analyze({"alpha": 90})
        assert out["style"] == "QUANT"
        assert out["score"] == 90

    def test_run_compat(self):
        # V1.0 委员会接口保持不变
        out = QuantAgent("q").run({"alpha": 90})
        assert out["agent"] == "q"
        assert out["score"] == 90


class TestMacroAgent:
    def test_easy_env(self):
        out = MacroAgent().analyze({"rate": "DOWN", "liquidity": "HIGH"})
        assert out["score"] == 90

    def test_tight_env(self):
        assert MacroAgent().analyze({"rate": "UP", "liquidity": "LOW"})["score"] == 50


class TestArena:
    def test_compete(self):
        team = create_team()
        results = StrategyArena(team).compete({"pe": 20, "roe": 20, "momentum": 1, "volume": 2, "alpha": 90})
        assert len(results) == 3
        assert {r["style"] for r in results} == {"VALUE", "TREND", "QUANT"}


class TestRanking:
    def test_rank_order(self):
        r = StrategyRanking().rank([{"style": "A", "score": 60}, {"style": "B", "score": 90}])
        assert r[0]["style"] == "B"

    def test_top_strategy(self):
        r = StrategyRanking().top_strategy([{"style": "A", "score": 60}, {"style": "B", "score": 90}])
        assert r["style"] == "B"


class TestVoting:
    def test_buy_majority(self):
        out = VotingSystem().vote([{"score": 90}, {"score": 85}, {"score": 70}])
        assert out["decision"] == "BUY"
        assert out["votes"]["BUY"] == 2

    def test_sell_majority(self):
        out = VotingSystem().vote([{"score": 30}, {"score": 20}, {"score": 70}])
        assert out["decision"] == "SELL"

    def test_hold(self):
        out = VotingSystem().vote([{"score": 65}, {"score": 70}, {"score": 30}])
        assert out["decision"] == "HOLD"


class TestInvestmentCommittee:
    def test_meeting(self):
        team = create_team()
        out = InvestmentCommittee(team).meeting(
            {"pe": 20, "roe": 20, "momentum": 1, "volume": 2, "alpha": 90}
        )
        assert len(out["opinions"]) == 3
        assert out["decision"]["decision"] in ("BUY", "HOLD", "SELL")


class TestRiskAgent:
    def test_high(self):
        assert RiskAgent().check([{"risk": 0.4}])["action"] == "REDUCE"

    def test_normal(self):
        assert RiskAgent().check([{"risk": 0.1}, {"risk": 0.2}])["action"] == "KEEP"


class TestCapitalAllocator:
    def test_weighted(self):
        out = CapitalAllocator().allocate([{"style": "A", "score": 75}, {"style": "B", "score": 25}], 1000)
        assert out[0]["weight"] == 0.75
        assert out[0]["capital"] == 750
        assert out[1]["capital"] == 250

    def test_zero_total(self):
        assert CapitalAllocator().allocate([{"style": "A", "score": 0}], 1000) == []


class TestChampion:
    def test_deploy(self):
        out = ChampionStrategy().deploy([{"style": "QUANT", "score": 90}, {"style": "TREND", "score": 80}])
        assert out["status"] == "DEPLOYED"
        assert out["strategy"] == "QUANT"


class TestChampionDB:
    def test_save_all(self, tmp_path):
        db = ChampionDB(str(tmp_path / "c.db"))
        try:
            db.save("QUANT", 90.0, "2026-09-09")
            rows = db.all()
            assert len(rows) == 1
            assert rows[0]["strategy"] == "QUANT"
        finally:
            db.close()
