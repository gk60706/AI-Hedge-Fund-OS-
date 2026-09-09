"""V1.2 Self-Evolving AI Hedge Fund Agent 测试"""
import pandas as pd
import pytest

from evolution.alpha_agent import AlphaAgent
from evolution.strategy_agent import StrategyAgent
from evolution.evolution_engine import EvolutionEngine
from evolution.code_agent import generate_code, _client

from optimizer.parameter_search import optimize

from genome.strategy_db import StrategyDB

from backtest.metrics import evaluate
from backtest.engine import BacktestEngine


class TestAlphaAgent:
    def test_discover_returns_valid_factor(self):
        agent = AlphaAgent()
        out = agent.discover(None)
        assert out["factor"] in agent.factors
        assert out["formula"]

    def test_generate_formula_known(self):
        assert AlphaAgent().generate_formula("momentum") == "close/close_20-1"

    def test_generate_formula_unknown_raises(self):
        with pytest.raises(KeyError):
            AlphaAgent().generate_formula("unknown_factor")


class TestStrategyAgent:
    def test_create(self):
        out = StrategyAgent().create({"factor": "momentum", "formula": "close/close_20-1"})
        assert out["name"] == "AI_momentum"
        assert out["entry"] == "close/close_20-1>0"
        assert out["exit"] == "drawdown>8%"
        assert out["position"] == 0.2


class TestCodeAgent:
    def test_no_key_raises(self, monkeypatch):
        from backend.config import get_settings

        monkeypatch.setenv("OPENAI_API_KEY", "")
        get_settings.cache_clear()
        try:
            with pytest.raises(RuntimeError):
                _client()
        finally:
            get_settings.cache_clear()


class TestOptimizer:
    def test_grid_search_finds_best(self):
        def backtest(config):
            return {"score": config["a"] * 10 + config["b"]}

        best = optimize({"a": [1, 2], "b": [1, 2]}, backtest)
        assert best == {"a": 2, "b": 2}

    def test_empty_params(self):
        assert optimize({}, lambda c: {"score": 0}) is None


class TestStrategyDB:
    def test_save_and_all(self, tmp_path):
        db = StrategyDB(str(tmp_path / "t.db"))
        try:
            db.save({"name": "AI_x", "score": 90.0, "code": "pass"})
            rows = db.all()
            assert len(rows) == 1
            assert rows[0]["name"] == "AI_x"
            assert rows[0]["score"] == 90.0
        finally:
            db.close()


class TestEvaluate:
    @pytest.mark.parametrize(
        "ret,expected",
        [(0.3, 50), (0.15, 30), (0.05, 0), (-0.1, -50)],
    )
    def test_scores(self, ret, expected):
        assert evaluate({"return": ret})["score"] == expected


class TestBacktestEngine:
    def test_buy_hold_sell(self):
        data = pd.DataFrame(
            {
                "price": [10, 12, 11, 14, 13],
                "signal": ["BUY", "HOLD", "HOLD", "SELL", "HOLD"],
            }
        )
        engine = BacktestEngine(initial_capital=1000)
        out = engine.run(data, lambda row: row["signal"])
        # 1000/10=100 股，14 卖出 → 1400
        assert out["capital"] == pytest.approx(1400)
        assert out["return"] == pytest.approx(0.4)

    def test_hold_to_end_settles(self):
        data = pd.DataFrame({"price": [10, 12], "signal": ["BUY", "HOLD"]})
        engine = BacktestEngine(initial_capital=1000)
        out = engine.run(data, lambda row: row["signal"])
        # 100 股按最后价 12 结算 → 1200
        assert out["capital"] == pytest.approx(1200)
