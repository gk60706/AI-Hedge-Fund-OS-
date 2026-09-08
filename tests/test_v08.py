"""V0.8 实时交易系统（盘中模拟）测试"""
import pytest

from realtime.tick_engine import TickEngine
from realtime.kline_engine import KlineEngine
from realtime.capital_monitor import capital_flow_score
from realtime.monitor import TradingMonitor

from intraday.momentum_agent import limit_up_agent
from intraday.stop_agent import take_profit_stop, stop_loss
from intraday.t0_agent import t0_strategy
from intraday.decision_agent import intraday_decision

from risk.alert import risk_alert


class TestTickEngine:
    def test_update_get(self):
        eng = TickEngine()
        eng.update({"code": "300394", "price": 10.0})
        assert eng.get("300394")["price"] == 10.0
        assert eng.get("000001") is None


class TestKlineEngine:
    def test_aggregate(self):
        eng = KlineEngine()
        eng.add_tick({"code": "A", "price": 1.0, "volume": 100})
        eng.add_tick({"code": "A", "price": 1.1, "volume": 200})
        df = eng.get_dataframe("A")
        assert len(df) == 2
        assert list(df.columns) == ["price", "volume"]


class TestCapitalMonitor:
    @pytest.mark.parametrize(
        "ticks,expected",
        [
            ([{"direction": "BUY", "amount": 400}, {"direction": "SELL", "amount": 100}], 95),
            ([{"direction": "BUY", "amount": 100}, {"direction": "SELL", "amount": 0}], 100),
            ([{"direction": "BUY", "amount": 50}, {"direction": "SELL", "amount": 100}], 30),
        ],
    )
    def test_scores(self, ticks, expected):
        assert capital_flow_score(ticks) == expected


class TestMomentumAgent:
    def test_limit_up(self):
        assert limit_up_agent(11.0, 10.0)["signal"] == "LIMIT_UP"

    def test_normal(self):
        assert limit_up_agent(10.5, 10.0)["signal"] == "NORMAL"


class TestStopAgent:
    def test_take_profit(self):
        assert take_profit_stop(10, 12.5)["action"] == "SELL"

    def test_hold_under_profit(self):
        assert take_profit_stop(10, 11.0)["action"] == "HOLD"

    def test_stop_loss(self):
        assert stop_loss(10, 9.0)["action"] == "SELL"

    def test_hold_over_loss(self):
        assert stop_loss(10, 9.5)["action"] == "HOLD"


class TestT0Agent:
    def test_buy_dip(self):
        assert t0_strategy(10.0, 9.5)["action"] == "BUY"

    def test_sell_high(self):
        assert t0_strategy(10.0, 10.6)["action"] == "SELL"

    def test_hold(self):
        assert t0_strategy(10.0, 10.1)["action"] == "HOLD"


class TestDecisionAgent:
    def test_buy(self):
        out = intraday_decision([{"score": 90}, {"score": 85}, {"score": 95}])
        assert out["action"] == "BUY"

    def test_sell(self):
        out = intraday_decision([{"score": 30}, {"score": 35}, {"score": 40}])
        assert out["action"] == "SELL"

    def test_hold(self):
        out = intraday_decision([{"score": 60}, {"score": 55}, {"score": 65}])
        assert out["action"] == "HOLD"


class TestRiskAlert:
    def test_alert_on_loss(self):
        alerts = risk_alert([{"code": "A", "loss": -0.1}])
        assert alerts == [{"code": "A", "warning": "跌破止损"}]

    def test_no_alert(self):
        assert risk_alert([{"code": "A", "loss": -0.05}]) == []


class TestTradingMonitor:
    def test_decision_after_three_signals(self, capsys):
        mon = TradingMonitor()
        mon.receive({"score": 90})
        mon.receive({"score": 85})
        mon.receive({"score": 95})
        captured = capsys.readouterr()
        assert "AI交易" in captured.out
        assert mon.signals == []
