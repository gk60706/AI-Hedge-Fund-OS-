"""V2.3 实时市场感知系统（Real-Time Market Intelligence Engine）单元测试。"""

import json

import pytest

from realtime.websocket_client import MarketWebSocket, MarketWebSocketV23
from realtime.tick_stream import TickStream
from realtime.market_cache import MarketCache
from realtime.radar.capital_radar import CapitalRadar
from realtime.radar.orderbook_analyzer import OrderBookAnalyzer
from realtime.radar.anomaly_detector import AnomalyDetector
from realtime.trading.intraday_agent import IntradayTrader
from realtime.risk.realtime_risk import RealTimeRisk


class TestMarketWebSocketV23:
    def test_subscribe_sends_message(self):
        sent = {}

        class FakeWS:
            def send(self, msg):
                sent["msg"] = msg

        ws = MarketWebSocketV23("wss://example.market.com")
        fake = FakeWS()
        ws.subscribe(fake, ["300394", "600519"])
        payload = json.loads(sent["msg"])
        assert payload["type"] == "subscribe"
        assert payload["symbols"] == ["300394", "600519"]

    def test_old_v08_interface_kept(self):
        # V0.8 异步版 MarketWebSocket（register + async connect）必须仍可导入使用
        mws = MarketWebSocket()
        got = []
        mws.register(lambda t: got.append(t))
        assert mws.callbacks
        assert mws.url == "wss://example.market.com"


class TestTickStream:
    def test_push_and_latest(self):
        ts = TickStream()
        ts.push({"code": "300394", "price": 10.0})
        ts.push({"code": "300394", "price": 10.2})
        out = ts.latest(1)
        assert len(out) == 1
        assert out[0]["price"] == 10.2
        assert "time" in out[0]

    def test_latest_default_100(self):
        ts = TickStream()
        for i in range(120):
            ts.push({"code": "x", "i": i})
        assert len(ts.latest()) == 100

    def test_old_v15_interface_kept(self):
        # V1.5 旧接口：update/get 必须仍可用
        ts = TickStream()
        ts.update({"code": "600519", "price": 1500.0})
        assert ts.get("600519")["price"] == 1500.0


class TestMarketCache:
    def test_save_get(self, monkeypatch):
        store = {}

        class FakeRedis:
            def set(self, k, v):
                store[k] = v

            def get(self, k):
                return store.get(k)

        def fake_redis(*args, **kwargs):
            return FakeRedis()

        monkeypatch.setattr("realtime.market_cache.redis.Redis", fake_redis)
        cache = MarketCache()
        cache.save("300394", {"price": 10.5})
        assert cache.get("300394") == {"price": 10.5}

    def test_get_missing(self, monkeypatch):
        class FakeRedis:
            def set(self, k, v):
                pass

            def get(self, k):
                return None

        monkeypatch.setattr("realtime.market_cache.redis.Redis", lambda *a, **k: FakeRedis())
        assert MarketCache().get("000000") is None


class TestCapitalRadar:
    def test_accumulation(self):
        out = CapitalRadar().analyze(
            {"volume_ratio": 3, "buy_amount": 800000, "sell_amount": 300000, "price_change": 2}
        )
        assert out["capital_score"] == 100
        assert out["signal"] == "ACCUMULATION"

    def test_wait(self):
        out = CapitalRadar().analyze(
            {"volume_ratio": 1, "buy_amount": 100, "sell_amount": 500, "price_change": -1}
        )
        assert out["capital_score"] == 0
        assert out["signal"] == "WAIT"


class TestOrderBookAnalyzer:
    def test_main_force_buy(self):
        out = OrderBookAnalyzer().analyze({"bid": [10000, 9000, 8000], "ask": [3000, 2000, 1000]})
        assert out["signal"] == "MAIN_FORCE_BUY"

    def test_normal(self):
        out = OrderBookAnalyzer().analyze({"bid": [1000, 1000, 1000], "ask": [3000, 3000, 3000]})
        assert out["signal"] == "NORMAL"


class TestAnomalyDetector:
    def test_fast_rise(self):
        out = AnomalyDetector().detect({"change": 6, "volume_ratio": 2})
        assert "FAST_RISE" in out

    def test_volume_spike(self):
        out = AnomalyDetector().detect({"change": 2, "volume_ratio": 6})
        assert "VOLUME_SPIKE" in out

    def test_both(self):
        out = AnomalyDetector().detect({"change": 8, "volume_ratio": 7})
        assert set(out) == {"FAST_RISE", "VOLUME_SPIKE"}

    def test_none(self):
        assert AnomalyDetector().detect({"change": 1, "volume_ratio": 1}) == []


class TestIntradayTrader:
    def test_buy(self):
        radar = {"capital_score": 80, "signal": "ACCUMULATION"}
        book = {"signal": "MAIN_FORCE_BUY"}
        assert IntradayTrader().decide(radar, book) == {"action": "BUY", "position": 0.1}

    def test_wait_low_score(self):
        radar = {"capital_score": 50, "signal": "WAIT"}
        book = {"signal": "MAIN_FORCE_BUY"}
        assert IntradayTrader().decide(radar, book)["action"] == "WAIT"

    def test_wait_no_signal(self):
        radar = {"capital_score": 90, "signal": "ACCUMULATION"}
        book = {"signal": "NORMAL"}
        assert IntradayTrader().decide(radar, book)["action"] == "WAIT"


class TestRealTimeRisk:
    def test_stop_trading(self):
        out = RealTimeRisk().check({"loss": -0.05, "position": 0.3})
        assert out["status"] == "STOP_TRADING"

    def test_reduce_position(self):
        out = RealTimeRisk().check({"loss": 0.0, "position": 0.6})
        assert out["status"] == "REDUCE_POSITION"

    def test_normal(self):
        out = RealTimeRisk().check({"loss": 0.01, "position": 0.3})
        assert out["status"] == "NORMAL"
