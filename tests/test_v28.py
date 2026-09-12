"""V2.8/V2.8.1 自动策略发现与进化系统（Auto Strategy Evolution Engine）单元测试。"""

import numpy as np
import pytest

from evolution.strategy_generator import StrategyGeneratorV28, StrategyGeneratorV281
from evolution.genetic_algorithm import GeneticAlgorithm, GeneticAlgorithmV281
from strategy_lab.strategy import Strategy, StrategyDNA, StrategyV281
from strategy_lab.evaluator import StrategyEvaluator, StrategyEvaluatorV281
from strategy_lab.leaderboard import StrategyLeaderboard, StrategyLeaderboardV281
from strategy_lab.lifecycle import StrategyLifecycle, StrategyLifecycleV281
from strategy_lab.signal_engine import StrategySignalEngine
from backtest.engine import BacktestEngineV281
from automl.optimizer import AutoOptimizer


class TestStrategyV28:
    def test_mutate(self):
        s = Strategy({"value": 0.5, "momentum": 0.5})
        s.mutate()
        assert 0 <= s.genes["value"] <= 1 or 0 <= s.genes["momentum"] <= 1


class TestStrategyGeneratorV28:
    def test_generate(self):
        genes = StrategyGeneratorV28().generate()
        assert set(genes.keys()) == {"value", "momentum", "capital", "holding"}
        assert 5 <= genes["holding"] <= 60


class TestStrategyEvaluatorV28:
    def test_evaluate(self):
        out = StrategyEvaluator().evaluate({})
        assert "score" in out
        assert out["return"] == 0.25


class TestStrategyLeaderboardV28:
    def test_rank(self):
        board = StrategyLeaderboard()
        board.add("a", 1.0)
        board.add("b", 2.0)
        assert board.rank()[0]["strategy"] == "b"


class TestStrategyLifecycleV28:
    def test_kill(self):
        assert StrategyLifecycle().check({"drawdown": -0.3, "sharpe": 0.5}) == "KILL"

    def test_promote(self):
        assert StrategyLifecycle().check({"drawdown": -0.05, "sharpe": 2.5}) == "PROMOTE"

    def test_test(self):
        assert StrategyLifecycle().check({"drawdown": -0.05, "sharpe": 1.0}) == "TEST"


class TestAutoOptimizer:
    def test_search(self):
        params = [{"score": 1}, {"score": 3}, {"score": 2}]
        assert AutoOptimizer().search(params) == {"score": 3}


class TestStrategyDNA:
    def test_to_dict(self):
        dna = StrategyDNA(0.5, 0.5, 0.5, 0.5, 0.7, 0.1, 0.2, 20, 0.1)
        out = dna.to_dict()
        assert out["holding_period"] == 20
        assert out["buy_threshold"] == 0.7


class TestStrategyV281:
    def test_mutate_keeps_bounds(self):
        dna = StrategyDNA(0.5, 0.5, 0.5, 0.5, 0.7, 0.1, 0.2, 20, 0.1)
        s = StrategyV281(dna)
        s.mutate()
        assert 0 <= s.dna.momentum_weight <= 1
        assert s.status == "EXPERIMENT"


class TestStrategyGeneratorV281:
    def test_generate_population(self):
        gen = StrategyGeneratorV281()
        pop = gen.generate_population(10)
        assert len(pop) == 10
        assert isinstance(pop[0], StrategyV281)


class TestBacktestEngineV281:
    def test_no_signals_flat(self):
        prices = [100] * 5
        signals = [0] * 5
        out = BacktestEngineV281().run(prices, signals, initial_cash=100000)
        assert np.allclose(out, 100000)

    def test_buy_sell_profit(self):
        prices = [100, 100, 100, 110, 110]
        signals = [1, 0, 0, -1, 0]
        out = BacktestEngineV281().run(prices, signals, initial_cash=100000)
        assert out[-1] > 100000


class TestStrategySignalEngine:
    def test_generate_shapes(self):
        dna = StrategyDNA(1.0, 0.0, 0.0, 0.0, 0.7, 0.1, 0.2, 20, 0.1)
        s = StrategyV281(dna)
        features = {"momentum": np.array([0.9, 0.5, 0.1]), "value": np.zeros(3),
                    "capital": np.zeros(3), "volume": np.zeros(3)}
        signals = StrategySignalEngine().generate(s, features)
        assert signals[0] == 1
        assert signals[2] == -1


class TestStrategyEvaluatorV281:
    def test_evaluate_flat(self):
        out = StrategyEvaluatorV281().evaluate([100, 100, 100])
        assert out["total_return"] == pytest.approx(0)
        assert out["score"] == pytest.approx(0)

    def test_evaluate_short(self):
        out = StrategyEvaluatorV281().evaluate([100])
        assert out["score"] == -999


class TestGeneticAlgorithmV281:
    def test_evolve_size(self):
        gen = StrategyGeneratorV281()
        pop = gen.generate_population(20)
        for s in pop:
            s.metrics = {"score": 1.0}
        out = GeneticAlgorithmV281().evolve(pop, 50)
        assert len(out) == 50

    def test_select(self):
        gen = StrategyGeneratorV281()
        pop = gen.generate_population(5)
        for i, s in enumerate(pop):
            s.metrics = {"score": float(i)}
        elites = GeneticAlgorithmV281().select(pop, 3)
        assert len(elites) == 3
        assert elites[0].metrics["score"] == 4.0


class TestStrategyLeaderboardV281:
    def test_rank(self):
        gen = StrategyGeneratorV281()
        pop = gen.generate_population(3)
        for i, s in enumerate(pop):
            s.metrics = {"score": float(i)}
        ranked = StrategyLeaderboardV281().rank(pop)
        assert ranked[0].metrics["score"] == 2.0
        assert len(StrategyLeaderboardV281().top(pop, 2)) == 2


class TestStrategyLifecycleV281:
    def test_no_metrics(self):
        assert StrategyLifecycleV281().evaluate(StrategyV281(StrategyDNA(0.5, 0.5, 0.5, 0.5, 0.7, 0.1, 0.2, 20, 0.1))) == "EXPERIMENT"

    def test_retired(self):
        s = StrategyV281(StrategyDNA(0.5, 0.5, 0.5, 0.5, 0.7, 0.1, 0.2, 20, 0.1))
        s.metrics = {"max_drawdown": -0.25, "sharpe": 1.0}
        assert StrategyLifecycleV281().evaluate(s) == "RETIRED"

    def test_validation(self):
        s = StrategyV281(StrategyDNA(0.5, 0.5, 0.5, 0.5, 0.7, 0.1, 0.2, 20, 0.1))
        s.metrics = {"max_drawdown": -0.10, "sharpe": 1.8}
        assert StrategyLifecycleV281().evaluate(s) == "VALIDATION"
