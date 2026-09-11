"""V2.5 量化交易风控中心（Institutional Risk Control Engine）单元测试。"""

import numpy as np
import pytest

from risk_engine.var_model import VaRModel
from risk_engine.drawdown_monitor import DrawdownMonitor
from risk_engine.volatility import VolatilityMonitor
from risk_engine.market_regime import MarketRegime
from risk_engine.black_swan import BlackSwanDetector
from risk_committee.risk_agent import RiskAgent
from risk_committee.risk_vote import RiskCommittee
from portfolio.risk_budget import RiskBudget


class TestVaRModel:
    def test_var_95(self):
        returns = np.array([0.01, -0.02, -0.03, 0.02, -0.05, 0.03, -0.01, -0.04])
        out = VaRModel().calculate(returns, 0.95)
        # 排序后第 int(8*0.05)=0 个，即最小值 -0.05
        assert out == -0.05

    def test_var_90(self):
        returns = np.array([-0.01, -0.02, -0.03, -0.04, -0.05])
        out = VaRModel().calculate(returns, 0.90)
        # losses=sort → [-0.05,-0.04,-0.03,-0.02,-0.01]; index=int(5*0.1)=0 → losses[0]
        assert out == -0.05


class TestDrawdownMonitor:
    def test_calculate(self):
        eq = [100, 120, 90, 110]
        assert DrawdownMonitor().calculate(eq) == pytest.approx(-0.25)

    def test_no_drawdown(self):
        assert DrawdownMonitor().calculate([100, 110, 120]) == 0

    def test_check_stop(self):
        assert DrawdownMonitor().check(-0.2) == "STOP"
        assert DrawdownMonitor().check(-0.05) == "NORMAL"


class TestVolatilityMonitor:
    def test_level_high(self):
        assert VolatilityMonitor().level(0.5) == "HIGH"

    def test_level_medium(self):
        assert VolatilityMonitor().level(0.3) == "MEDIUM"

    def test_level_low(self):
        assert VolatilityMonitor().level(0.1) == "LOW"

    def test_calculate_positive(self):
        out = VolatilityMonitor().calculate(np.array([0.01, -0.01, 0.02, -0.02]))
        assert out >= 0


class TestMarketRegime:
    def test_bull(self):
        assert MarketRegime().detect(0.15, 0.1) == "BULL"

    def test_bear(self):
        assert MarketRegime().detect(-0.05, 0.5) == "BEAR"

    def test_sideway(self):
        assert MarketRegime().detect(0.02, 0.15) == "SIDEWAY"


class TestBlackSwanDetector:
    def test_crash(self):
        out = BlackSwanDetector().detect({"drop": -0.06, "volatility": 0.3})
        assert "MARKET_CRASH" in out

    def test_volatility_spike(self):
        out = BlackSwanDetector().detect({"drop": -0.02, "volatility": 0.7})
        assert "VOLATILITY_SPIKE" in out

    def test_none(self):
        assert BlackSwanDetector().detect({"drop": -0.01, "volatility": 0.2}) == []


class TestRiskBudget:
    def test_equal_weight(self):
        out = RiskBudget().allocate(["a", "b", "c", "d"])
        assert out == {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}


class TestRiskAgent:
    def test_approve(self):
        assert RiskAgent().review({"code": "x", "position": 0.1}, {"volatility": 0.2}) == "APPROVE"

    def test_reject_high_vol(self):
        assert RiskAgent().review({"code": "x", "position": 0.1}, {"volatility": 0.6}) == "REJECT"

    def test_reject_high_position(self):
        assert RiskAgent().review({"code": "x", "position": 0.4}, {"volatility": 0.2}) == "REJECT"


class TestRiskCommittee:
    def test_approve(self):
        assert RiskCommittee().vote(["APPROVE", "APPROVE", "APPROVE"]) == "APPROVE"

    def test_reject_two(self):
        assert RiskCommittee().vote(["REJECT", "REJECT", "APPROVE"]) == "REJECT"

    def test_one_reject_ok(self):
        assert RiskCommittee().vote(["REJECT", "APPROVE", "APPROVE"]) == "APPROVE"
