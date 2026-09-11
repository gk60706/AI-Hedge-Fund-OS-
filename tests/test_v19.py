"""V1.9 AI 策略自动进化系统 单元测试。"""

import pytest

from strategy.strategy_template import StrategyDNA
from evolution.strategy_generator import StrategyGenerator
from evolution.strategy_population import StrategyPopulation
from evolution.factor_miner import FactorMiner
from evolution.genetic_optimizer import GeneticOptimizer
from evolution.evolution_engine import EvolutionEngine
from alpha.alpha_score import AlphaScore


def _dna(ma_fast=10, ma_slow=30, rsi_buy=30, rsi_sell=70,
         volume_factor=2.0, stop_loss=0.05, take_profit=0.15):
    return StrategyDNA(
        ma_fast=ma_fast, ma_slow=ma_slow, rsi_buy=rsi_buy, rsi_sell=rsi_sell,
        volume_factor=volume_factor, stop_loss=stop_loss, take_profit=take_profit,
    )


class TestStrategyDNA:
    def test_mutation_returns_self(self):
        dna = _dna()
        assert dna.mutation() is dna

    def test_mutation_changes_fields(self):
        dna = _dna()
        orig = (dna.ma_fast, dna.rsi_buy, dna.volume_factor)
        dna.mutation()
        # 变异至少改变一个字段（randint 有可能为 0，但 volume_factor 恒变）
        assert dna.volume_factor != orig[2]


class TestStrategyGenerator:
    def test_generate_valid_dna(self):
        dna = StrategyGenerator().generate()
        assert isinstance(dna, StrategyDNA)
        assert 3 <= dna.ma_fast <= 20
        assert 20 <= dna.ma_slow <= 120
        assert 20 <= dna.rsi_buy <= 40
        assert 60 <= dna.rsi_sell <= 90
        assert 1.2 <= dna.volume_factor <= 3


class TestStrategyPopulation:
    def test_add_and_size(self):
        pop = StrategyPopulation()
        pop.add(_dna())
        pop.add(_dna())
        assert pop.size() == 2


class TestFactorMiner:
    def test_search_combinations(self):
        combos = FactorMiner().search(["ma", "rsi", "vol", "mom"])
        # C(4,2) + C(4,3) = 6 + 4 = 10
        assert len(combos) == 10
        assert all(2 <= len(c) <= 3 for c in combos)


class TestGeneticOptimizer:
    def test_select_top10(self):
        pop = [_dna(ma_fast=i) for i in range(30)]
        scores = list(range(30))
        best = GeneticOptimizer().select(pop, scores)
        assert len(best) == 10
        # 最高分 29 的策略应被选中
        assert best[0] == pop[29]

    def test_crossover_ma_fast_mean(self):
        p1 = _dna(ma_fast=10)
        p2 = _dna(ma_fast=20)
        child = GeneticOptimizer().crossover(p1, p2)
        assert child.ma_fast == 15
        # 不污染父本
        assert p1.ma_fast == 10

    def test_mutate(self):
        s = _dna()
        out = GeneticOptimizer().mutate(s)
        assert out is s


class TestAlphaScore:
    def test_calculate(self):
        score = AlphaScore().calculate(
            {"return": 0.2, "sharpe": 1.5, "drawdown": -0.1, "win_rate": 0.6}
        )
        assert score == pytest.approx(0.2 * 40 + 1.5 * 30 - 0.1 * 20 + 0.6 * 10)


class TestEvolutionEngine:
    def test_create_population(self):
        gen = StrategyGenerator()
        opt = GeneticOptimizer()
        engine = EvolutionEngine(gen, opt)
        assert len(engine.create_population(100)) == 100

    def test_evolve_selects_top(self):
        gen = StrategyGenerator()
        opt = GeneticOptimizer()
        engine = EvolutionEngine(gen, opt)
        pop = [_dna(ma_fast=i) for i in range(30)]
        scores = list(range(30))
        nxt = engine.evolve(pop, scores)
        assert len(nxt) == 10
