"""V0.7 模拟盘交易系统（Paper Trading Engine）测试"""
import pytest

from trading.account import Account
from trading.order import Order
from trading.position import Position
from trading.broker import PaperBroker
from trading.execution import execute_trade
from trading.performance import calculate_pnl
from trading.portfolio import Portfolio
from database.trade_db import TradeDB
from agents.trader_agent import trader_agent


class TestAccount:
    def test_init(self):
        acc = Account(cash=100000)
        assert acc.cash == 100000
        assert acc.total_asset == 100000

    def test_update_asset(self):
        acc = Account(cash=10000)
        acc.positions = {"300394": {"volume": 100, "cost": 9000}}
        acc.update_asset({"300394": 120})
        assert acc.total_asset == 10000 + 120 * 100

    def test_get_balance(self):
        acc = Account(cash=5000)
        b = acc.get_balance()
        assert b["cash"] == 5000
        assert b["asset"] == 5000


class TestOrder:
    def test_to_dict(self):
        o = Order(code="300394", action="BUY", price=120, volume=1000)
        d = o.to_dict()
        assert d["code"] == "300394"
        assert d["action"] == "BUY"
        assert d["price"] == 120
        assert d["volume"] == 1000
        assert "time" in d


class TestPosition:
    def test_buy_accumulates_cost(self):
        p = Position()
        p.buy("A", 10, 100)
        p.buy("A", 20, 100)
        pos = p.get_positions()["A"]
        assert pos["volume"] == 200
        assert pos["cost"] == 10 * 100 + 20 * 100

    def test_sell_reduces(self):
        p = Position()
        p.buy("A", 10, 100)
        p.sell("A", 40)
        assert p.get_positions()["A"]["volume"] == 60


class TestPaperBroker:
    def test_execute_buy(self):
        b = PaperBroker()
        r = b.execute(Order("300394", "BUY", 120, 1000))
        assert r["status"] == "FILLED"
        assert b.position.get_positions()["300394"]["volume"] == 1000
        assert len(b.orders) == 1

    def test_execute_sell(self):
        b = PaperBroker()
        b.execute(Order("A", "BUY", 10, 100))
        b.execute(Order("A", "SELL", 10, 40))
        assert b.position.get_positions()["A"]["volume"] == 60


class TestExecution:
    def test_execute_trade(self):
        r = execute_trade({"code": "300394", "action": "BUY", "price": 120, "volume": 1000})
        assert r["status"] == "FILLED"
        assert r["order"]["code"] == "300394"


class TestPerformance:
    def test_pnl(self):
        out = calculate_pnl({"A": {"volume": 100, "cost": 1000}}, {"A": 15})
        assert out[0]["code"] == "A"
        assert out[0]["pnl"] == 1500 - 1000
        assert out[0]["return"] == 0.5


class TestPortfolio:
    def test_snapshot(self):
        pf = Portfolio(cash=10000)
        pf.account.positions = {"A": {"volume": 100, "cost": 8000}}
        snap = pf.snapshot({"A": 90})
        assert snap["balance"]["asset"] == 10000 + 9000
        assert snap["pnl"][0]["code"] == "A"


class TestTradeDB:
    def test_insert(self, tmp_path):
        db = TradeDB(db_path=str(tmp_path / "t.db"))
        db.insert({"code": "300394", "action": "BUY", "price": 120, "volume": 1000, "time": "now"})
        rows = db.conn.execute("SELECT count(*) FROM trades").fetchone()
        assert rows[0] == 1


class TestTraderAgent:
    @pytest.mark.parametrize("score,action", [(90, "BUY"), (30, "SELL"), (60, "HOLD")])
    def test_actions(self, score, action):
        sig = trader_agent({"code": "300394", "score": score, "price": 120})
        assert sig["action"] == action
        assert sig["volume"] == 1000
