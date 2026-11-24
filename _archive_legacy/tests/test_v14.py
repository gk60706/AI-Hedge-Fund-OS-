"""V1.4 自动交易生产系统测试"""
import pytest

from scanner.stock_scanner import StockScanner
from scanner.ranking import StockRanking

from trading.broker import PaperBroker
from trading.position import Position, PositionManager
from trading.rebalance import RebalanceEngine

from reports.daily_report import generate_report

from notification.email import send_email

from database.mysql import database_url, engine
from database.models import Base, Stock


class _FakeAgent:
    def __init__(self, score):
        self._score = score

    def analyze(self, stock):
        return {"score": self._score}


class TestStockScanner:
    def test_scan_avg(self):
        stocks = [{"code": "A"}, {"code": "B"}]
        out = StockScanner([_FakeAgent(80), _FakeAgent(60)]).scan(stocks)
        assert out[0]["code"] == "A"
        assert out[0]["score"] == 70
        assert len(out) == 2

    def test_scan_empty_agents(self):
        out = StockScanner([]).scan([{"code": "A"}])
        assert out[0]["score"] == 0


class TestStockRanking:
    def test_select_top(self):
        out = StockRanking().select(
            [{"code": "A"}, {"code": "B"}, {"code": "C"}], number=2
        )
        assert [r["code"] for r in out] == ["A", "B"]


class TestPaperBrokerV14:
    def test_buy_sell(self):
        b = PaperBroker(capital=1000)
        assert b.buy("300394", 10, 100) is True
        assert b.cash == 0
        assert b.positions["300394"] == {"price": 10, "amount": 100}
        assert b.sell("300394") is True
        assert "300394" not in b.positions

    def test_buy_insufficient(self):
        b = PaperBroker(capital=100)
        assert b.buy("A", 10, 100) is False

    def test_v07_execute_compat(self):
        from trading.order import Order

        b = PaperBroker()
        b.execute(Order(code="300394", action="BUY", price=10, volume=100))
        assert b.position.get_positions()["300394"]["volume"] == 100
        assert b.positions["300394"]["amount"] == 100


class TestPositionManager:
    def test_summary(self):
        b = PaperBroker(capital=500)
        b.buy("A", 5, 100)
        out = PositionManager().summary(b)
        assert out["cash"] == 0
        assert "A" in out["positions"]


class TestRebalance:
    def test_rebalance_buys_top5(self):
        b = PaperBroker(capital=100000)
        stocks = [{"code": f"S{i}", "price": 10.0} for i in range(6)]
        out = RebalanceEngine().rebalance(stocks, b)
        assert len(out) == 5
        assert "S5" not in out


class TestDailyReport:
    def test_report(self):
        text = generate_report({"A": 1})
        assert "AI Hedge Fund Daily Report" in text
        assert "今日组合" in text


class TestEmail:
    def test_simulated(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "")
        monkeypatch.setenv("SMTP_USER", "")
        monkeypatch.setenv("SMTP_PASSWORD", "")
        monkeypatch.setenv("SMTP_TO", "")
        assert send_email("hello") == "SIMULATED"


class TestDatabase:
    def test_url_no_secret_in_code(self):
        url = database_url()
        assert url.startswith("mysql+pymysql://")
        assert "password" not in url  # 未配置时密码为空，不硬编码

    def test_engine_lazy(self):
        # create_engine 惰性，仅 import 不触发真实连接
        assert engine is not None

    def test_models(self):
        assert Stock.__tablename__ == "stocks"
        assert hasattr(Stock, "code")
        assert Base is not None
