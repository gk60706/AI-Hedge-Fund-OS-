"""V0.6 AI 多策略交易引擎（模拟组合）测试"""
import numpy as np
import pytest

from strategies.momentum_strategy import momentum_score
from strategies.value_strategy import value_score
from strategies.capital_strategy import capital_score
from strategies.multi_factor import calculate_factor

from portfolio.optimizer import markowitz_optimizer
from portfolio.risk_model import calculate_risk
from portfolio.allocator import risk_budget
from portfolio.rebalance import rebalance
from agents.portfolio_agent import portfolio_manager
from portfolio.main_engine import run_portfolio


class TestMomentumStrategy:
    def test_high_momentum(self):
        assert momentum_score({"return_30": 0.3}) == 80

    def test_mid_momentum(self):
        assert momentum_score({"return_30": 0.1}) == 65

    def test_negative_momentum(self):
        assert momentum_score({"return_30": -0.1}) == 30

    def test_clamped(self):
        assert momentum_score({"return_30": 0.5}) <= 100


class TestValueStrategy:
    @pytest.mark.parametrize("pe,expected", [(10, 90), (20, 70), (40, 50), (80, 20)])
    def test_pe_buckets(self, pe, expected):
        assert value_score({"pe": pe}) == expected

    def test_default_pe(self):
        assert value_score({}) == 50


class TestCapitalStrategy:
    @pytest.mark.parametrize("buy,sell,expected", [(400, 100, 95), (250, 100, 80), (150, 100, 60), (50, 100, 30)])
    def test_ratio_buckets(self, buy, sell, expected):
        assert capital_score({"buy_volume": buy, "sell_volume": sell}) == expected


class TestMultiFactor:
    def test_calculate_factor(self):
        stock = {"code": "300394", "return_30": 0.3, "pe": 40, "buy_volume": 50000, "sell_volume": 10000}
        out = calculate_factor(stock)
        assert out["code"] == "300394"
        assert out["factor_detail"]["momentum"] == 80
        assert out["factor_detail"]["value"] == 50
        assert out["factor_detail"]["capital"] == 95
        # 80*0.4 + 50*0.3 + 95*0.3 = 32+15+28.5 = 75.5
        assert out["alpha"] == pytest.approx(75.5)


class TestOptimizer:
    def test_markowitz_weights_sum_to_one(self):
        returns = np.array([[0.1, 0.2, 0.15], [0.05, 0.1, 0.08], [0.12, 0.05, 0.1]])
        w = markowitz_optimizer(returns)
        assert len(w) == 3
        assert sum(w) == pytest.approx(1.0, abs=1e-6)


class TestRiskModel:
    def test_normal_risk(self):
        out = calculate_risk([{"volatility": 0.2}, {"volatility": 0.25}])
        assert out["portfolio_risk"] == pytest.approx(0.225)
        assert out["level"] == "NORMAL"

    def test_high_risk(self):
        out = calculate_risk([{"volatility": 0.4}])
        assert out["level"] == "HIGH"


class TestAllocator:
    def test_equal_weight(self):
        out = risk_budget([{"code": "A"}, {"code": "B"}], 1000)
        assert len(out) == 2
        assert all(x["weight"] == 0.5 for x in out)
        assert sum(x["capital"] for x in out) == 1000


class TestRebalance:
    def test_buy_and_sell(self):
        orders = rebalance([{"code": "A"}], [{"code": "B"}])
        actions = {o["action"] for o in orders}
        assert actions == {"BUY", "SELL"}

    def test_no_change(self):
        assert rebalance([{"code": "A"}], [{"code": "A"}]) == []


class TestPortfolioAgent:
    def test_top10_equal_weight(self):
        stocks = [{"code": f"S{i}", "alpha": float(i)} for i in range(20)]
        out = portfolio_manager(stocks, money=100000)
        assert len(out) == 10
        assert out[0]["code"] == "S19"
        assert all(x["capital"] == 10000 for x in out)
        assert all(x["position"] == 0.1 for x in out)


class TestMainEngine:
    def test_run_portfolio(self):
        stocks = [
            {"code": "300394", "return_30": 0.35, "pe": 40, "buy_volume": 50000, "sell_volume": 10000},
            {"code": "000001", "return_30": -0.1, "pe": 10, "buy_volume": 100, "sell_volume": 500},
        ]
        out = run_portfolio(stocks)
        assert len(out) <= 10
        assert all("code" in x and "alpha" in x for x in out)
