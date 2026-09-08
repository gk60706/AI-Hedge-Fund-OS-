"""V0.5 回测引擎 + Alpha 因子系统 测试"""
import pandas as pd
import pytest

from factors.momentum import momentum_factor
from factors.value import pe_factor
from factors.capital import capital_factor
from factors.factor_engine import calculate_alpha, rank_stocks

from backtest.metrics import max_drawdown, sharpe
from ai.strategy_agent import evaluate_strategy
from ai.optimizer import objective


class TestMomentumFactor:
    def test_adds_momentum_column(self):
        df = pd.DataFrame({"close": [10, 11, 12, 13, 14, 15]})
        out = momentum_factor(df, period=3)
        assert "momentum" in out.columns

    def test_momentum_value(self):
        df = pd.DataFrame({"close": [10, 10, 10, 10, 12, 12]})
        out = momentum_factor(df, period=4)
        # close[-1]=12, close[-5]=10 -> 0.2
        assert abs(out["momentum"].iloc[-1] - 0.2) < 1e-9

    def test_returns_same_dataframe(self):
        df = pd.DataFrame({"close": [1, 2, 3]})
        assert momentum_factor(df, period=1) is df


class TestValueFactor:
    @pytest.mark.parametrize("pe,expected", [(10, 90), (30, 70), (60, 50), (100, 20)])
    def test_pe_buckets(self, pe, expected):
        assert pe_factor(pe) == expected


class TestCapitalFactor:
    def test_zero_sell_volume(self):
        assert capital_factor(100, 0) == 100

    @pytest.mark.parametrize("buy,sell,expected", [(400, 100, 100), (250, 100, 80), (150, 100, 60), (50, 100, 30)])
    def test_ratio_buckets(self, buy, sell, expected):
        assert capital_factor(buy, sell) == expected


class TestFactorEngine:
    def test_calculate_alpha_positive_momentum(self):
        closes = list(range(10, 32))  # 22 行递增，20 日动量为正
        df = pd.DataFrame({"close": closes})
        assert calculate_alpha(df) == 40

    def test_calculate_alpha_negative_momentum(self):
        closes = list(range(31, 9, -1))  # 22 行递减，20 日动量为负
        df = pd.DataFrame({"close": closes})
        assert calculate_alpha(df) == 20

    def test_rank_stocks_desc(self):
        stocks = [{"alpha": 30}, {"alpha": 90}, {"alpha": 60}]
        ranked = rank_stocks(stocks)
        assert [s["alpha"] for s in ranked] == [90, 60, 30]


class TestBacktestMetrics:
    def test_max_drawdown(self):
        values = [100, 120, 90, 110, 80]
        # peak=120 -> dd=(120-80)/120=0.3333
        assert abs(max_drawdown(values) - 0.3333) < 1e-3

    def test_sharpe(self):
        returns = [0.1, -0.05, 0.2]
        import numpy as np
        expected = np.mean(returns) / np.std(returns)
        assert sharpe(returns) == pytest.approx(expected)


class TestStrategyAgent:
    def test_keep(self):
        r = {"return": 0.3, "drawdown": 0.1, "sharpe": 1.5}
        out = evaluate_strategy(r)
        assert out["score"] >= 80
        assert out["status"] == "KEEP"

    def test_drop(self):
        r = {"return": 0.05, "drawdown": 0.3, "sharpe": 0.2}
        out = evaluate_strategy(r)
        assert out["status"] == "DROP"

    def test_missing_keys_defaults(self):
        out = evaluate_strategy({"return": 0.15})
        assert 0 <= out["score"] <= 100


class TestOptimizerObjective:
    def test_objective_returns_float(self):
        class FakeTrial:
            def suggest_int(self, name, low, high):
                return low

        score = objective(FakeTrial())
        assert isinstance(score, float)
