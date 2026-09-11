"""V2.4 盘中自主交易系统（Autonomous Trading Execution Layer）单元测试。"""

import json

import pytest

from execution.order import Order
from execution.broker import Broker
from execution.simulator import SimulatorBroker
from execution.qmt_gateway import QMTGateway
from portfolio.account import Account
from portfolio.position import PositionManager
from strategy.signal_engine import SignalEngine
from risk.position_control import PositionControl
from risk.stop_manager import StopManager
from journal.trade_log import TradeJournal


class TestOrder:
    def test_order_fields(self):
        o = Order(code="300394", side="BUY", price=120.0, quantity=100)
        assert o.code == "300394"
        assert o.side == "BUY"
        assert o.price == 120.0
        assert o.quantity == 100
        assert o.time


class TestBroker:
    def test_abstract_raises(self):
        with pytest.raises(NotImplementedError):
            Broker().send_order(None)


class TestSimulatorBroker:
    def test_buy_fills(self):
        acc = Account(1000000)
        broker = SimulatorBroker(acc)
        res = broker.send_order(Order(code="300394", side="BUY", price=120, quantity=100))
        assert res["status"] == "FILLED"
        assert acc.cash == 1000000 - 120 * 100
        assert acc.positions["300394"] == 100

    def test_sell_reduces(self):
        acc = Account(1000000)
        broker = SimulatorBroker(acc)
        broker.send_order(Order(code="300394", side="BUY", price=100, quantity=200))
        broker.send_order(Order(code="300394", side="SELL", price=110, quantity=50))
        assert acc.positions["300394"] == 150


class TestAccount:
    def test_value(self):
        acc = Account(1000000)
        acc.positions["300394"] = 100
        assert acc.value({"300394": 120.0}) == 1000000 + 100 * 120.0

    def test_default_cash(self):
        assert Account().cash == 1000000


class TestPositionManager:
    def test_check(self):
        acc = Account()
        acc.positions["300394"] = 100
        out = PositionManager().check(acc)
        assert out["stocks"] == 1
        assert out["positions"]["300394"] == 100


class TestSignalEngine:
    def test_buy(self):
        assert SignalEngine().generate({"capital": 90, "risk": "LOW"}) == "BUY"

    def test_wait_low_capital(self):
        assert SignalEngine().generate({"capital": 50, "risk": "LOW"}) == "WAIT"

    def test_wait_high_risk(self):
        assert SignalEngine().generate({"capital": 90, "risk": "HIGH"}) == "WAIT"


class TestPositionControl:
    def test_scores(self):
        pc = PositionControl()
        assert pc.calculate(95) == 0.2
        assert pc.calculate(85) == 0.1
        assert pc.calculate(75) == 0.05
        assert pc.calculate(60) == 0


class TestStopManager:
    def test_stop_loss(self):
        assert StopManager().check(100, 91) == "STOP_LOSS"

    def test_take_profit(self):
        assert StopManager().check(100, 121) == "TAKE_PROFIT"

    def test_hold(self):
        assert StopManager().check(100, 105) == "HOLD"


class TestTradeJournal:
    def test_record_and_save(self, tmp_path):
        j = TradeJournal()
        j.record({"code": "300394", "side": "BUY", "qty": 100})
        p = tmp_path / "trades.json"
        j.save(str(p))
        data = json.loads(p.read_text(encoding="utf8"))
        assert data[0]["code"] == "300394"


class TestQMTGateway:
    def test_gateway_placeholder(self, capsys):
        g = QMTGateway()
        g.connect()
        g.buy("300394", 100)
        out = capsys.readouterr().out
        assert "QMT接口等待连接" in out
        assert "QMT BUY" in out
