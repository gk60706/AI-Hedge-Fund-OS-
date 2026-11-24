# -*- coding: utf-8 -*-
"""V3.3 真实组合优化引擎 + V3.4 机构级 Ensemble Portfolio Optimizer 测试。"""
import numpy as np
import pandas as pd
import pytest


# ============================================================
# V3.3 data/historical.py
# ============================================================
class TestHistorical:
    def test_normalize_code(self):
        from data.historical import normalize_code
        assert normalize_code("300394") == "300394"
        assert normalize_code("sh600519") == "600519"
        assert normalize_code("SZ000001") == "000001"
        assert normalize_code("bj430047") == "430047"

    def test_normalize_code_invalid(self):
        from data.historical import normalize_code
        with pytest.raises(ValueError):
            normalize_code("abc")
        with pytest.raises(ValueError):
            normalize_code("12345")


# ============================================================
# V3.3 factors/returns.py
# ============================================================
class TestReturns:
    def test_calculate_returns(self):
        from factors.returns import calculate_returns
        df = pd.DataFrame({"close": [10.0, 11.0, 12.1]})
        returns = calculate_returns(df)
        assert len(returns) == 2
        assert returns.iloc[0] == pytest.approx(0.10)
        assert returns.iloc[1] == pytest.approx(0.10)

    def test_calculate_returns_missing_column(self):
        from factors.returns import calculate_returns
        with pytest.raises(ValueError):
            calculate_returns(pd.DataFrame({"x": [1.0]}))


# ============================================================
# V3.3 portfolio/covariance.py
# ============================================================
class TestCovariance:
    def test_calculate_annualized(self):
        from portfolio.covariance import CovarianceEngine
        engine = CovarianceEngine()
        df = pd.DataFrame({"A": [0.01, -0.02, 0.01], "B": [0.02, 0.0, -0.01]})
        cov = engine.calculate(df, annualize=True)
        assert "A" in cov.columns and "B" in cov.columns
        assert cov.loc["A", "A"] >= 0

    def test_portfolio_volatility(self):
        from portfolio.covariance import CovarianceEngine
        engine = CovarianceEngine()
        cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.04]], index=["A", "B"], columns=["A", "B"])
        vol = engine.portfolio_volatility({"A": 0.5, "B": 0.5}, cov)
        assert vol == pytest.approx(np.sqrt(0.02))


# ============================================================
# V3.3 portfolio/transaction_cost.py
# ============================================================
class TestTransactionCost:
    def test_estimate_sell_includes_stamp_duty(self):
        from portfolio.transaction_cost import TransactionCostModel
        model = TransactionCostModel()
        cost_sell = model.estimate(1_000_000, "SELL")
        cost_buy = model.estimate(1_000_000, "BUY")
        assert cost_sell > cost_buy
        assert cost_sell == pytest.approx(
            1_000_000 * (0.0003 + 0.0005 + 0.0005),
        )
        assert cost_buy == pytest.approx(
            1_000_000 * (0.0003 + 0.0005),
        )


# ============================================================
# V3.3 portfolio/target_portfolio.py
# ============================================================
class TestTargetPosition:
    def test_delta(self):
        from portfolio.target_portfolio import TargetPosition
        pos = TargetPosition(code="600519", target_weight=0.15, current_weight=0.05)
        assert pos.delta == pytest.approx(0.10)


# ============================================================
# V3.3/V3.4 portfolio/position_sizer.py
# ============================================================
class TestPositionSizer:
    def test_shares_from_weight(self):
        from portfolio.position_sizer import PositionSizer
        sizer = PositionSizer()
        shares = sizer.shares_from_weight(1_000_000, 0.10, 100.0)
        assert shares == 1000

    def test_calculate_zero_guard(self):
        from portfolio.position_sizer import PositionSizer
        sizer = PositionSizer()
        result = sizer.calculate(1_000_000, 0.10, 0.0)
        assert result["shares"] == 0

    def test_calculate_rounding(self):
        from portfolio.position_sizer import PositionSizer
        sizer = PositionSizer()
        result = sizer.calculate(1_000_000, 0.15, 1400.0)
        assert result["shares"] == 100
        assert result["actual_weight"] == pytest.approx(0.14)


# ============================================================
# V3.3 portfolio/rebalancer.py
# ============================================================
class TestRebalancer:
    def test_generate_orders(self):
        from portfolio.rebalancer import Rebalancer
        rebalancer = Rebalancer(min_trade_weight=0.02)
        orders = rebalancer.generate_orders(
            current_positions={"A": 0.10, "B": 0.05},
            target_positions={"A": 0.15, "B": 0.03},
            prices={"A": 100.0, "B": 50.0},
            total_equity=1_000_000,
        )
        assert len(orders) == 2
        sides = {o["code"]: o["side"] for o in orders}
        assert sides["A"] == "BUY"
        assert sides["B"] == "SELL"

    def test_min_trade_weight_skipped(self):
        from portfolio.rebalancer import Rebalancer
        rebalancer = Rebalancer(min_trade_weight=0.02)
        orders = rebalancer.generate_orders(
            current_positions={"A": 0.10},
            target_positions={"A": 0.105},
            prices={"A": 100.0},
            total_equity=1_000_000,
        )
        assert orders == []

    def test_orders_sorted_by_trade_value(self):
        from portfolio.rebalancer import Rebalancer
        rebalancer = Rebalancer(min_trade_weight=0.01)
        orders = rebalancer.generate_orders(
            current_positions={"A": 0.10, "B": 0.05},
            target_positions={"A": 0.12, "B": 0.20},
            prices={"A": 100.0, "B": 50.0},
            total_equity=1_000_000,
        )
        values = [o["trade_value"] for o in orders]
        assert values == sorted(values, reverse=True)


# ============================================================
# V3.3 portfolio/rebalance_decision.py
# ============================================================
class TestRebalanceDecision:
    def test_decide(self):
        from portfolio.rebalance_decision import RebalanceDecisionEngine
        engine = RebalanceDecisionEngine(min_expected_alpha=0.02)
        assert engine.decide(0.10, 0.01) == "BUY"
        assert engine.decide(-0.10, 0.01) == "SELL"
        assert engine.decide(0.01, 0.0) == "HOLD"


# ============================================================
# V3.4 portfolio/liquidity.py
# ============================================================
class TestLiquidity:
    def test_allowed_weight(self):
        from portfolio.liquidity import LiquidityConstraint
        constraint = LiquidityConstraint(max_participation=0.10)
        assert constraint.max_trade_value(10_000_000) == pytest.approx(1_000_000)
        assert constraint.allowed_weight(1_000_000, 10_000_000) == pytest.approx(1.0)
        assert constraint.allowed_weight(10_000_000, 10_000_000) == pytest.approx(0.10)


# ============================================================
# V3.4 portfolio/turnover.py
# ============================================================
class TestTurnover:
    def test_calculate_turnover(self):
        from portfolio.turnover import TurnoverController
        controller = TurnoverController(max_turnover=0.30)
        turnover = controller.calculate_turnover(
            {"A": 0.10, "B": 0.05},
            {"A": 0.20, "B": 0.0},
        )
        assert turnover == pytest.approx(0.15)
        assert controller.allowed({"A": 0.10}, {"A": 0.20}) is True
        assert controller.allowed({"A": 0.10}, {"A": 0.60}) is False


# ============================================================
# V3.4 risk/constraints.py
# ============================================================
class TestRiskConstraints:
    def test_checks(self):
        from risk.constraints import RiskConstraintEngine
        engine = RiskConstraintEngine()
        assert engine.check_single_stock(0.15) is True
        assert engine.check_single_stock(0.25) is False
        assert engine.check_industry(0.30) is True
        assert engine.check_industry(0.35) is False
        assert engine.check_beta(1.05) is True
        assert engine.check_beta(1.20) is False
        assert engine.check_cash(0.08) is True
        assert engine.check_cash(0.02) is False


# ============================================================
# V3.4 optimization/mean_variance.py
# ============================================================
class TestMeanVariance:
    def test_optimize(self):
        from optimization.mean_variance import MeanVarianceOptimizer
        optimizer = MeanVarianceOptimizer(max_weight=0.20)
        cov = np.array([[0.04, 0.0], [0.0, 0.04]])
        weights = optimizer.optimize(
            expected_returns={"A": 0.20, "B": 0.10},
            covariance=cov,
            codes=["A", "B"],
        )
        assert set(weights) == {"A", "B"}
        assert sum(weights.values()) == pytest.approx(1.0)
        assert all(w >= 0 for w in weights.values())

    def test_optimize_empty(self):
        from optimization.mean_variance import MeanVarianceOptimizer
        assert MeanVarianceOptimizer().optimize({}, np.array([]), []) == {}


# ============================================================
# V3.4 optimization/risk_parity.py
# ============================================================
class TestRiskParity:
    def test_optimize(self):
        from optimization.risk_parity import RiskParityOptimizer
        optimizer = RiskParityOptimizer()
        cov = np.diag([0.04, 0.16])
        # 无单票上限时权重与 1/σ 成正比
        weights = optimizer.optimize(cov, ["A", "B"], max_weight=1.0)
        assert weights["A"] > weights["B"]
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_optimize_max_weight_cap(self):
        from optimization.risk_parity import RiskParityOptimizer
        optimizer = RiskParityOptimizer()
        cov = np.diag([0.04, 0.16])
        weights = optimizer.optimize(cov, ["A", "B"])
        # cap 后重新归一化，权重仍非负且和为 1
        assert all(w >= 0 for w in weights.values())
        assert sum(weights.values()) == pytest.approx(1.0)


# ============================================================
# V3.4 optimization/black_litterman.py
# ============================================================
class TestBlackLitterman:
    def test_posterior(self):
        from optimization.black_litterman import BlackLittermanModel
        model = BlackLittermanModel()
        cov = np.diag([0.04, 0.16])
        market = np.array([0.5, 0.5])
        views = np.array([0.2, 0.1])
        posterior = model.calculate_posterior_returns(
            covariance=cov,
            market_weights=market,
            views=views,
            view_confidence=np.array([1.0, 0.0]),
        )
        assert posterior[0] == pytest.approx(0.2)
        assert posterior[1] == pytest.approx(2.5 * 0.16 * 0.5)


# ============================================================
# V3.4 optimization/ensemble.py
# ============================================================
class TestEnsemble:
    def test_combine(self):
        from optimization.ensemble import EnsembleOptimizer
        ensemble = EnsembleOptimizer()
        result = ensemble.combine(
            mean_variance={"A": 0.6, "B": 0.4},
            risk_parity={"A": 0.4, "B": 0.6},
            black_litterman={"A": 0.5, "B": 0.5},
            alpha_scores={"A": 80, "B": 60},
        )
        assert set(result) == {"A", "B"}
        assert sum(result.values()) == pytest.approx(1.0)


# ============================================================
# V3.4 optimization/objective.py
# ============================================================
class TestObjective:
    def test_calculate(self):
        from optimization.objective import PortfolioObjective
        objective = PortfolioObjective()
        value = objective.calculate(
            expected_return=0.20,
            volatility=0.15,
            turnover=0.05,
            transaction_cost=0.01,
        )
        assert value == pytest.approx(0.20 - 2.0 * 0.15 - 0.5 * 0.05 - 0.01)


# ============================================================
# V3.4 portfolio/optimizer.py InstitutionalPortfolioOptimizer
# ============================================================
class TestInstitutionalOptimizer:
    def test_optimize(self):
        from portfolio.optimizer import InstitutionalPortfolioOptimizer
        optimizer = InstitutionalPortfolioOptimizer()
        codes = ["300394", "688568", "300274", "002594", "600519", "601318"]
        volatility = np.array([0.32, 0.28, 0.30, 0.25, 0.20, 0.18])
        correlation = np.array(
            [
                [1.00, 0.45, 0.50, 0.40, 0.20, 0.15],
                [0.45, 1.00, 0.35, 0.30, 0.15, 0.10],
                [0.50, 0.35, 1.00, 0.55, 0.20, 0.15],
                [0.40, 0.30, 0.55, 1.00, 0.25, 0.20],
                [0.20, 0.15, 0.20, 0.25, 1.00, 0.35],
                [0.15, 0.10, 0.15, 0.20, 0.35, 1.00],
            ],
        )
        covariance = np.diag(volatility) @ correlation @ np.diag(volatility)
        weights = optimizer.optimize(
            codes=codes,
            covariance=covariance,
            expected_returns=np.array([0.18, 0.14, 0.16, 0.13, 0.10, 0.09]),
            alpha_scores={
                "300394": 88, "688568": 82, "300274": 84,
                "002594": 80, "600519": 76, "601318": 73,
            },
        )
        assert set(weights) == set(codes)
        assert sum(weights.values()) == pytest.approx(1.0)
        assert all(w <= 0.20 + 1e-9 for w in weights.values())

    def test_optimize_empty(self):
        from portfolio.optimizer import InstitutionalPortfolioOptimizer
        assert InstitutionalPortfolioOptimizer().optimize([], [], [], {}) == {}


# ============================================================
# V3.4 portfolio/institutional_manager.py
# ============================================================
class TestInstitutionalManager:
    def test_size_positions(self):
        from portfolio.institutional_manager import InstitutionalPortfolioManager
        manager = InstitutionalPortfolioManager()
        positions = manager.size_positions(
            weights={"600519": 0.14},
            prices={"600519": 1400.0},
            total_equity=1_000_000,
        )
        assert positions["600519"]["shares"] == 100

    def test_apply_liquidity_constraint(self):
        from portfolio.institutional_manager import InstitutionalPortfolioManager
        manager = InstitutionalPortfolioManager()
        result = manager.apply_liquidity_constraint(
            weights={"A": 0.50, "B": 0.50},
            liquidity={"A": 1_000_000, "B": 1_000_000},
            total_equity=10_000_000,
        )
        assert sum(result.values()) == pytest.approx(1.0)
        assert result["A"] == pytest.approx(0.50)


# ============================================================
# V3.3 portfolio/portfolio_manager.py PortfolioManagerV33
# ============================================================
class TestPortfolioManagerV33:
    def test_build_target_portfolio(self):
        from portfolio.portfolio_manager import PortfolioManagerV33
        manager = PortfolioManagerV33()
        candidates = [
            {"code": "300394", "name": "天孚通信", "alpha_score": 88,
             "volatility": 0.32, "beta": 1.20, "industry": "通信"},
            {"code": "688568", "name": "中科星图", "alpha_score": 82,
             "volatility": 0.28, "beta": 1.10, "industry": "软件"},
            {"code": "300274", "name": "阳光电源", "alpha_score": 84,
             "volatility": 0.30, "beta": 1.15, "industry": "光伏"},
            {"code": "002594", "name": "比亚迪", "alpha_score": 80,
             "volatility": 0.25, "beta": 1.05, "industry": "汽车"},
            {"code": "600519", "name": "贵州茅台", "alpha_score": 76,
             "volatility": 0.20, "beta": 0.85, "industry": "白酒"},
            {"code": "601318", "name": "中国平安", "alpha_score": 73,
             "volatility": 0.18, "beta": 0.80, "industry": "保险"},
        ]
        result = manager.build_target_portfolio(
            candidates=candidates,
            portfolio_volatility=0.20,
            max_drawdown=-0.05,
            market_score=72,
            top_n=6,
        )
        assert "positions" in result and "cash" in result
        assert sum(result["positions"].values()) + result["cash"] == pytest.approx(1.0)

    def test_generate_rebalance_orders(self):
        from portfolio.portfolio_manager import PortfolioManagerV33
        manager = PortfolioManagerV33()
        orders = manager.generate_rebalance_orders(
            current_positions={"A": 0.10},
            target_positions={"A": 0.15},
            prices={"A": 100.0},
            total_equity=1_000_000,
        )
        assert len(orders) == 1
        assert orders[0]["side"] == "BUY"
