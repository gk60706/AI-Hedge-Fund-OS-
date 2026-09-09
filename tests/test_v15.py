"""V1.5 实时盘中交易平台测试"""
import pytest

from realtime.websocket import StockWebSocket
from realtime.tick_stream import TickStream
from realtime.orderbook import OrderBookAnalyzer

from capital.main_force import MainForceDetector

from intraday.momentum import MomentumAgent
from intraday.t0_strategy import T0Strategy
from intraday.trader_agent import IntradayTrader

from market.limit_strategy import LimitUpAgent
from market.dragon_tiger import DragonTigerAgent

from risk.realtime_risk import RealTimeRisk


class TestStockWebSocket:
    def test_subscribe(self):
        ws = StockWebSocket("ws://localhost:8000/quote")
        calls = []
        ws.subscribe(lambda t: calls.append(t))
        assert len(ws.handlers) == 1
        assert ws.url == "ws://localhost:8000/quote"


class TestTickStream:
    def test_update_get(self):
        ts = TickStream()
        ts.update({"code": "300394", "price": 10.0})
        assert ts.get("300394")["price"] == 10.0
        assert ts.get("000001") is None


class TestOrderBook:
    def test_buy_pressure(self):
        data = {f"bid{i}_volume": 10000 for i in range(1, 6)}
        data.update({f"ask{i}_volume": 1000 for i in range(1, 6)})
        out = OrderBookAnalyzer().analyze(data)
        assert out["signal"] == "BUY_PRESSURE"
        assert out["strength"] > 2

    def test_sell_pressure(self):
        data = {f"bid{i}_volume": 1000 for i in range(1, 6)}
        data.update({f"ask{i}_volume": 10000 for i in range(1, 6)})
        out = OrderBookAnalyzer().analyze(data)
        assert out["signal"] == "SELL_PRESSURE"


class TestMainForce:
    def test_detect(self):
        ticks = [
            {"amount": 1000000, "side": "BUY"},
            {"amount": 1000000, "side": "BUY"},
            {"amount": 100000, "side": "SELL"},
        ]
        out = MainForceDetector().detect(ticks)
        assert out["main_force_score"] > 50

    def test_small_orders_ignored(self):
        ticks = [{"amount": 1000, "side": "BUY"}]
        out = MainForceDetector().detect(ticks)
        assert out["main_force_score"] == 0


class TestMomentum:
    def test_high(self):
        assert MomentumAgent().score([10.0, 10.5]) == 90

    def test_mid(self):
        assert MomentumAgent().score([10.0, 10.1]) == 70

    def test_low(self):
        assert MomentumAgent().score([10.0, 9.5]) == 40


class TestT0:
    def test_buy(self):
        assert T0Strategy().decide(-0.05, 90)["action"] == "BUY"

    def test_sell(self):
        assert T0Strategy().decide(0.06, 50)["action"] == "SELL"

    def test_hold(self):
        assert T0Strategy().decide(0.01, 50)["action"] == "HOLD"


class TestIntradayTrader:
    def test_buy(self):
        assert IntradayTrader().decide([90, 85, 80]) == "BUY"

    def test_sell(self):
        assert IntradayTrader().decide([30, 20, 40]) == "SELL"

    def test_hold(self):
        assert IntradayTrader().decide([60, 50]) == "HOLD"

    def test_empty(self):
        assert IntradayTrader().decide([]) == "HOLD"


class TestLimitUp:
    def test_limit(self):
        out = LimitUpAgent().check(11.0, 10.0)
        assert out["signal"] == "LIMIT_UP"
        assert out["score"] == 100

    def test_normal(self):
        assert LimitUpAgent().check(10.5, 10.0)["signal"] == "NORMAL"


class TestDragonTiger:
    def test_institution(self):
        out = DragonTigerAgent().analyze({"institution_buy": 20000000})
        assert out["signal"] == "机构抢筹"

    def test_normal(self):
        assert DragonTigerAgent().analyze({})["signal"] == "普通交易"


class TestRealTimeRisk:
    def test_alert(self):
        out = RealTimeRisk().check([{"code": "A", "loss": -0.10}])
        assert out[0]["action"] == "SELL"

    def test_no_alert(self):
        assert RealTimeRisk().check([{"code": "A", "loss": -0.05}]) == []
