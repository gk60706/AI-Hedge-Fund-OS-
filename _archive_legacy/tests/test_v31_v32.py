# -*- coding: utf-8 -*-
"""V3.1 - V3.2 测试。

覆盖：
- V3.1 AI Portfolio Manager（factors/alpha_score、PortfolioConstraints、
  PortfolioOptimizerV31、PortfolioManagerV31、risk/portfolio_risk、main_v31）
- V3.2 Dynamic Risk Budget + Portfolio Optimization（factors/beta、
  RiskParity、VolatilityTarget、IndustryRiskBudget、BetaController、
  DynamicCashManager、RiskStateEngine、DrawdownController、
  PortfolioOptimizerV32、PortfolioManagerV32、main_v32）
"""
import numpy as np
import pytest


# ---------------------------------------------------------------
# V3.1 factors/alpha_score
# ---------------------------------------------------------------
class TestAlphaScore:
    def test_calculate_basic(self):
        from factors.alpha_score import AlphaScore

        score = AlphaScore()
        alpha = score.calculate(
            {
                "fundamental_score": 88,
                "valuation_score": 60,
                "trend_score": 82,
                "capital_score": 85,
                "industry_score": 90,
                "risk_score": 70,
            }
        )
        # 88*.30 + 60*.15 + 82*.20 + 85*.15 + 90*.10 + 30*.10 = 76.55
        assert alpha == pytest.approx(76.55, abs=0.01)

    def test_calculate_clamp(self):
        from factors.alpha_score import AlphaScore

        score = AlphaScore()
        high = score.calculate(
            {
                "fundamental_score": 100,
                "valuation_score": 100,
                "trend_score": 100,
                "capital_score": 100,
                "industry_score": 100,
                "risk_score": 0,
            }
        )
        assert high == pytest.approx(100.0)
        low = score.calculate(
            {
                "fundamental_score": 0,
                "valuation_score": 0,
                "trend_score": 0,
                "capital_score": 0,
                "industry_score": 0,
                "risk_score": 100,
            }
        )
        assert low == pytest.approx(0.0)

    def test_missing_fields_default(self):
        from factors.alpha_score import AlphaScore

        alpha = AlphaScore().calculate({})
        assert 0.0 <= alpha <= 100.0


# ---------------------------------------------------------------
# V3.1 portfolio/constraints
# ---------------------------------------------------------------
class TestPortfolioConstraints:
    def test_valid_portfolio(self):
        from portfolio.constraints import PortfolioConstraints

        c = PortfolioConstraints(max_single_weight=0.20)
        result = c.validate(
            [
                {"code": "300394", "weight": 0.20},
                {"code": "600519", "weight": 0.18},
            ]
        )
        assert result["valid"] is True
        assert result["total_weight"] == pytest.approx(0.38)
        assert result["cash_weight"] == pytest.approx(0.62)

    def test_over_limit_single(self):
        from portfolio.constraints import PortfolioConstraints

        c = PortfolioConstraints(max_single_weight=0.20)
        result = c.validate([{"code": "300394", "weight": 0.25}])
        assert result["valid"] is False
        assert "over limit" in result["reason"]

    def test_over_total(self):
        from portfolio.constraints import PortfolioConstraints

        c = PortfolioConstraints(max_single_weight=0.20)
        result = c.validate(
            [
                {"code": "300394", "weight": 0.20},
                {"code": "600519", "weight": 0.20},
                {"code": "601318", "weight": 0.20},
                {"code": "688568", "weight": 0.20},
                {"code": "300750", "weight": 0.20},
                {"code": "002594", "weight": 0.20},
            ]
        )
        assert result["valid"] is False
        assert "exceeds" in result["reason"]


# ---------------------------------------------------------------
# V3.1 PortfolioOptimizerV31 / PortfolioManagerV31
# ---------------------------------------------------------------
class TestPortfolioManagerV31:
    def test_optimizer_v31_weight_budget(self):
        from portfolio.optimizer import PortfolioOptimizerV31

        opt = PortfolioOptimizerV31(
            max_positions=3,
            max_single_weight=0.20,
            cash_reserve=0.10,
        )
        ranked = [
            {"code": "300394", "alpha_score": 80, "volatility": 0.3},
            {"code": "600519", "alpha_score": 60, "volatility": 0.2},
            {"code": "601318", "alpha_score": 40, "volatility": 0.18},
            {"code": "688568", "alpha_score": 90, "volatility": 0.35},
        ]
        positions = opt.optimize(ranked)
        assert len(positions) == 3  # 只取前 max_positions
        total = sum(p["weight"] for p in positions)
        # 预算 0.90（保留 10% 现金），单票 cap 0.20 可能使总仓位更低
        assert total <= 0.90 + 1e-9
        assert all(p["weight"] <= 0.20 + 1e-9 for p in positions)

    def test_manager_v31_end_to_end(self):
        from portfolio.portfolio_manager import PortfolioManagerV31

        manager = PortfolioManagerV31(
            max_positions=5,
            max_single_weight=0.20,
        )
        candidates = [
            {"code": "300394", "name": "天孚通信", "fundamental_score": 88,
             "valuation_score": 60, "trend_score": 82, "capital_score": 85,
             "industry_score": 90, "risk_score": 70, "volatility": 0.35},
            {"code": "688568", "name": "中科星图", "fundamental_score": 80,
             "valuation_score": 55, "trend_score": 75, "capital_score": 70,
             "industry_score": 82, "risk_score": 72, "volatility": 0.30},
            {"code": "300750", "name": "宁德时代", "fundamental_score": 85,
             "valuation_score": 72, "trend_score": 65, "capital_score": 68,
             "industry_score": 70, "risk_score": 80, "volatility": 0.25},
            {"code": "600519", "name": "贵州茅台", "fundamental_score": 92,
             "valuation_score": 60, "trend_score": 55, "capital_score": 60,
             "industry_score": 65, "risk_score": 90, "volatility": 0.20},
            {"code": "601318", "name": "中国平安", "fundamental_score": 78,
             "valuation_score": 80, "trend_score": 60, "capital_score": 65,
             "industry_score": 68, "risk_score": 88, "volatility": 0.18},
        ]
        result = manager.build_portfolio(candidates)
        assert len(result["positions"]) == 5
        assert result["validation"]["valid"] is True
        assert result["validation"]["total_weight"] == pytest.approx(
            0.90, abs=0.01
        )
        assert result["validation"]["cash_weight"] == pytest.approx(
            0.10, abs=0.01
        )
        # 按 alpha 降序
        alphas = [p["alpha_score"] for p in result["positions"]]
        assert alphas == sorted(alphas, reverse=True)

    def test_main_v31_runs(self, capsys):
        import main_v31

        main_v31.main()
        out = capsys.readouterr().out
        assert "AI HEDGE FUND OS V3.1" in out
        assert "FINAL PORTFOLIO" in out
        assert "CONSTRAINT CHECK" in out
        assert "PORTFOLIO RISK" in out


# ---------------------------------------------------------------
# V3.1 risk/portfolio_risk
# ---------------------------------------------------------------
class TestPortfolioRisk:
    def test_analyze(self):
        from risk.portfolio_risk import PortfolioRisk

        risk = PortfolioRisk()
        positions = [
            {"code": "A", "weight": 0.20, "volatility": 0.35},
            {"code": "B", "weight": 0.18, "volatility": 0.30},
            {"code": "C", "weight": 0.18, "volatility": 0.25},
            {"code": "D", "weight": 0.17, "volatility": 0.20},
            {"code": "E", "weight": 0.17, "volatility": 0.18},
        ]
        result = risk.analyze(positions)
        total = sum(p["weight"] for p in positions)
        norm = [p["weight"] / total for p in positions]
        vols = [p["volatility"] for p in positions]
        expected_vol = sum(w * v for w, v in zip(norm, vols))
        assert result["portfolio_volatility"] == pytest.approx(
            expected_vol, abs=1e-3
        )
        assert 0.0 < result["concentration"] <= 1.0
        assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}

    def test_analyze_empty(self):
        from risk.portfolio_risk import PortfolioRisk

        result = PortfolioRisk().analyze([])
        assert result["portfolio_volatility"] == 0.0
        assert result["risk_level"] == "LOW"


# ---------------------------------------------------------------
# V3.2 factors/beta
# ---------------------------------------------------------------
class TestCalculateBeta:
    def test_length_mismatch(self):
        from factors.beta import calculate_beta

        with pytest.raises(ValueError):
            calculate_beta([0.01, 0.02], [0.01])

    def test_too_short(self):
        from factors.beta import calculate_beta

        assert calculate_beta([0.01], [0.01]) == 1.0

    def test_zero_benchmark_var(self):
        from factors.beta import calculate_beta

        assert calculate_beta([0.01, 0.02, 0.03], [0.0, 0.0, 0.0]) == 1.0

    def test_basic_value(self):
        from factors.beta import calculate_beta

        stock = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        bench = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        beta = calculate_beta(stock, bench)
        # Beta = cov(ddof=1) / var(ddof=0)，与实现公式一致
        expected = np.cov(stock, bench, ddof=1)[0, 1] / np.var(bench)
        assert beta == pytest.approx(expected, abs=1e-6)
        assert beta == pytest.approx(1.25, abs=1e-6)


# ---------------------------------------------------------------
# V3.2 factors/volatility & correlation
# ---------------------------------------------------------------
class TestFactorTools:
    def test_volatility_constant_returns(self):
        from factors.volatility import calculate_volatility

        assert calculate_volatility([0.01, 0.01, 0.01]) == 0.0

    def test_volatility_short(self):
        from factors.volatility import calculate_volatility

        assert calculate_volatility([0.01]) == 0.0

    def test_correlation(self):
        from factors.correlation import calculate_correlation

        a = [0.01, 0.02, 0.03, 0.04]
        b = [0.02, 0.04, 0.06, 0.08]
        assert calculate_correlation(a, b) == pytest.approx(1.0, abs=1e-6)

    def test_correlation_mismatch(self):
        from factors.correlation import calculate_correlation

        with pytest.raises(ValueError):
            calculate_correlation([0.01], [0.01, 0.02])


# ---------------------------------------------------------------
# V3.2 Risk Parity / Volatility Target
# ---------------------------------------------------------------
class TestRiskBudgetComponents:
    def test_risk_parity_inverse_vol(self):
        from portfolio.risk_parity import RiskParity

        weights = RiskParity().calculate_weights(
            {"A": 0.20, "B": 0.40},
            max_weight=1.0,
        )
        assert weights["A"] > weights["B"]  # 低波动占更高权重
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)

    def test_risk_parity_empty(self):
        from portfolio.risk_parity import RiskParity

        assert RiskParity().calculate_weights({}) == {}

    def test_volatility_target_zero(self):
        from portfolio.volatility_target import VolatilityTarget

        vt = VolatilityTarget()
        assert vt.calculate_exposure(0.0) == vt.max_exposure

    def test_volatility_target_scale(self):
        from portfolio.volatility_target import VolatilityTarget

        vt = VolatilityTarget(target_volatility=0.15)
        assert vt.calculate_exposure(0.30) == pytest.approx(0.50, abs=1e-6)
        # 上限
        assert vt.calculate_exposure(0.05) == pytest.approx(0.95, abs=1e-6)
        # 下限
        assert vt.calculate_exposure(1.0) == pytest.approx(0.20, abs=1e-6)


# ---------------------------------------------------------------
# V3.2 Industry Budget / Beta Control / Dynamic Cash
# ---------------------------------------------------------------
class TestRiskBudgetControls:
    def test_industry_budget_compress(self):
        from portfolio.industry_budget import IndustryRiskBudget

        weights = {"A": 0.20, "B": 0.20, "C": 0.20}
        industries = {"A": "AI", "B": "AI", "C": "消费"}
        result = IndustryRiskBudget(
            default_max_weight=0.30
        ).apply(weights, industries)
        # AI 合计 0.40 > 0.30，压缩到 0.30
        ai_total = result["A"] + result["B"]
        assert ai_total == pytest.approx(0.30, abs=1e-6)
        assert result["C"] == pytest.approx(0.20, abs=1e-6)

    def test_beta_control_within_limit(self):
        from portfolio.beta_control import BetaController

        bc = BetaController(target_beta=0.85, max_beta=1.10)
        weights = {"A": 0.5, "B": 0.5}
        betas = {"A": 0.8, "B": 0.9}
        result = bc.adjust(weights, betas)
        assert result == weights  # 组合 beta 0.85 <= 1.10 原样返回

    def test_beta_control_scale_down(self):
        from portfolio.beta_control import BetaController

        bc = BetaController(target_beta=0.85, max_beta=1.10)
        weights = {"A": 0.5, "B": 0.5}
        betas = {"A": 1.5, "B": 1.5}  # 组合 beta 1.5 > 1.10
        result = bc.adjust(weights, betas)
        assert result["A"] == pytest.approx(0.5 * 0.85 / 1.5, abs=1e-6)

    def test_dynamic_cash_escalation(self):
        from portfolio.dynamic_cash import DynamicCashManager

        dm = DynamicCashManager()
        base = dm.calculate_cash_ratio(0.10, -0.05, 70)
        assert base == pytest.approx(0.05, abs=1e-9)
        stressed = dm.calculate_cash_ratio(0.40, -0.25, 20)
        # 0.05 + 0.10 + 0.10 + 0.10 + 0.10 + 0.15 + 0.10 + 0.10 = 0.80 -> cap 0.60
        assert stressed == pytest.approx(0.60, abs=1e-9)


# ---------------------------------------------------------------
# V3.2 Risk State / Drawdown Control
# ---------------------------------------------------------------
class TestRiskState:
    def test_thresholds(self):
        from risk.risk_state import RiskState, RiskStateEngine

        engine = RiskStateEngine()
        assert engine.evaluate(-0.05, 0.15) == RiskState.NORMAL
        assert engine.evaluate(-0.06, 0.22) == RiskState.WARNING
        assert engine.evaluate(-0.10, 0.10) == RiskState.WARNING
        assert engine.evaluate(-0.16, 0.10) == RiskState.DEFENSIVE
        assert engine.evaluate(-0.05, 0.32) == RiskState.DEFENSIVE
        assert engine.evaluate(-0.21, 0.10) == RiskState.EMERGENCY
        assert engine.evaluate(-0.05, 0.42) == RiskState.EMERGENCY

    def test_main_v32_warning(self):
        from risk.risk_state import RiskState, RiskStateEngine

        state = RiskStateEngine().evaluate(
            max_drawdown=-0.06,
            portfolio_volatility=0.22,
        )
        assert state == RiskState.WARNING

    def test_drawdown_controller(self):
        from risk.drawdown_control import DrawdownController

        dc = DrawdownController()
        assert dc.calculate_exposure_multiplier(-0.05) == 1.00
        assert dc.calculate_exposure_multiplier(-0.10) == 0.85
        assert dc.calculate_exposure_multiplier(-0.13) == 0.70
        assert dc.calculate_exposure_multiplier(-0.18) == 0.50
        assert dc.calculate_exposure_multiplier(-0.23) == 0.30
        assert dc.calculate_exposure_multiplier(-0.30) == 0.15


# ---------------------------------------------------------------
# V3.2 PortfolioOptimizerV32 / PortfolioManagerV32
# ---------------------------------------------------------------
class TestPortfolioOptimizerV32:
    def test_empty_candidates(self):
        from portfolio.optimizer import PortfolioOptimizerV32

        result = PortfolioOptimizerV32().optimize(
            [], portfolio_volatility=0.2, max_drawdown=-0.05,
            market_score=60,
        )
        assert result["positions"] == {}
        assert result["cash"] == 1.0
        assert result["exposure"] == 0.0

    def test_pipeline(self):
        from portfolio.optimizer import PortfolioOptimizerV32

        candidates = [
            {"code": "300394", "volatility": 0.32, "alpha_score": 88,
             "industry": "AI光通信", "beta": 1.20},
            {"code": "688568", "volatility": 0.28, "alpha_score": 82,
             "industry": "卫星应用", "beta": 1.10},
            {"code": "300274", "volatility": 0.30, "alpha_score": 84,
             "industry": "新能源", "beta": 1.15},
            {"code": "002594", "volatility": 0.25, "alpha_score": 80,
             "industry": "新能源", "beta": 1.05},
            {"code": "600519", "volatility": 0.20, "alpha_score": 76,
             "industry": "消费", "beta": 0.85},
            {"code": "601318", "volatility": 0.18, "alpha_score": 73,
             "industry": "金融", "beta": 0.80},
        ]
        result = PortfolioOptimizerV32().optimize(
            candidates,
            portfolio_volatility=0.22,
            max_drawdown=-0.06,
            market_score=72,
        )
        assert set(result["positions"].keys()) == {
            "300394", "688568", "300274", "002594", "600519", "601318"
        }
        total = sum(result["positions"].values()) + result["cash"]
        assert total == pytest.approx(1.0, abs=1e-9)
        assert 0.0 <= result["exposure"] <= 0.95
        # exposure = target 0.15 / vol 0.22 * dd 1.0，market 72 不打折
        assert result["exposure"] == pytest.approx(0.15 / 0.22, abs=1e-6)

    def test_manager_v32(self):
        from portfolio.portfolio_manager import PortfolioManagerV32

        candidates = [
            {"code": "300394", "volatility": 0.32, "alpha_score": 88,
             "industry": "AI光通信", "beta": 1.20},
            {"code": "600519", "volatility": 0.20, "alpha_score": 76,
             "industry": "消费", "beta": 0.85},
            {"code": "601318", "volatility": 0.18, "alpha_score": 73,
             "industry": "金融", "beta": 0.80},
        ]
        result = PortfolioManagerV32().build_portfolio(
            candidates=candidates,
            portfolio_volatility=0.22,
            max_drawdown=-0.06,
            market_score=72,
            top_n=2,
        )
        assert result["selected_stocks"] == ["300394", "600519"]  # alpha 前 2
        assert set(result["positions"].keys()) == {"300394", "600519"}

    def test_main_v32_runs(self, capsys):
        import main_v32

        main_v32.main()
        out = capsys.readouterr().out
        assert "AI Hedge Fund OS V3.2" in out
        assert "Risk State: WARNING" in out
        assert "Portfolio" in out
        assert "Cash" in out
        assert "Exposure" in out
