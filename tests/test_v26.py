"""V2.6 组合优化与资金管理系统（Portfolio Intelligence Layer）单元测试。"""

import pytest

from portfolio.portfolio_manager import PortfolioManager
from portfolio.exposure import ExposureAnalyzer
from portfolio.attribution import Attribution
from portfolio_ai.scoring import AIStockScore
from portfolio_ai.optimizer import PortfolioOptimizer
from portfolio_ai.black_litterman import BlackLitterman
from portfolio_ai.asset_allocator import AssetAllocator
from portfolio_ai.rebalance import RebalanceEngine


class TestPortfolioManager:
    def test_add_and_check(self):
        pm = PortfolioManager()
        pm.add_position("300394", 0.2)
        pm.add_position("688568", 0.1)
        out = pm.check()
        assert out["positions"]["300394"] == 0.2
        assert out["total"] == pytest.approx(0.3)


class TestAIStockScore:
    def test_calculate(self):
        stock = {"fundamental": 90, "technical": 80, "capital": 70, "industry": 60}
        # 90*0.3 + 80*0.2 + 70*0.3 + 60*0.2 = 27 + 16 + 21 + 12 = 76
        assert AIStockScore().calculate(stock) == 76.0


class TestPortfolioOptimizer:
    def test_equal_weight(self):
        out = PortfolioOptimizer().optimize(["300394", "688568", "300750"])
        assert out == {"300394": 0.333, "688568": 0.333, "300750": 0.333}


class TestBlackLitterman:
    def test_adjust(self):
        out = BlackLitterman().adjust(
            {"300394": 0.05, "688568": 0.05},
            {"300394": 0.03},
        )
        assert out["300394"] == pytest.approx(0.08)
        assert out["688568"] == pytest.approx(0.05)


class TestAssetAllocator:
    def test_allocate(self):
        out = AssetAllocator().allocate({"300394": 95, "688568": 88, "300750": 75})
        assert out == {"300394": 0.2, "688568": 0.1, "300750": 0.05}


class TestRebalanceEngine:
    def test_no_orders(self):
        assert RebalanceEngine().rebalance({"a": 0.2}, {"a": 0.21}) == []

    def test_orders(self):
        out = RebalanceEngine().rebalance({"a": 0.2}, {"a": 0.3, "b": 0.05})
        assert {o["stock"] for o in out} == {"a"}
        assert out[0]["change"] == pytest.approx(0.1)


class TestExposureAnalyzer:
    def test_analyze(self):
        out = ExposureAnalyzer().analyze(
            {"300394": {"sector": "AI", "weight": 0.2}, "688568": {"sector": "AI", "weight": 0.1}}
        )
        assert out["AI"] == pytest.approx(0.3)


class TestAttribution:
    def test_analyze(self):
        out = Attribution().analyze({"AI算力": 0.05, "新能源": -0.01, "市场Beta": 0.02})
        assert out == {"AI算力": 0.05, "新能源": -0.01, "市场Beta": 0.02}
