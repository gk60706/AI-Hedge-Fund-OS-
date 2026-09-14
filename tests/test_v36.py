"""V3.6 真实 A 股数据研究平台测试。"""

import pandas as pd
import pytest

from data.akshare_client import AkShareClientV36
from data.calendar import TradingCalendar
from data.price_loader import PriceLoader
from market.limit_rules import LimitRule
from market.suspension import SuspensionDetector
from market.trading_rules import AShareTradingRules
from backtest.costs import TradingCostModel
from backtest.execution import ExecutionEngine, ExecutionResult
from validation.data_quality import DataQualityChecker


# ---------------------------------------------------------------
# AkShareClientV36
# ---------------------------------------------------------------


class TestAkShareClientV36:
    def test_get_daily_calls_akshare_and_caches(self, monkeypatch, tmp_path):
        df_in = pd.DataFrame(
            {
                "日期": ["2024-01-02", "2024-01-03"],
                "开盘": [10.0, 10.5],
                "收盘": [10.4, 10.8],
            }
        )

        def fake_hist(**kwargs):
            return df_in.copy()

        monkeypatch.setattr("data.akshare_client.ak.stock_zh_a_hist", fake_hist)
        client = AkShareClientV36(cache_dir=str(tmp_path))
        df = client.get_daily("000001", "20240101", "20240105")
        assert len(df) == 2

        # 第二次命中缓存，不再调用网络
        calls = []

        def fake_hist_2(**kwargs):
            calls.append(1)
            raise AssertionError("should hit cache")

        monkeypatch.setattr("data.akshare_client.ak.stock_zh_a_hist", fake_hist_2)
        df2 = client.get_daily("000001", "20240101", "20240105")
        assert len(df2) == 2
        assert calls == []

    def test_get_daily_empty_raises(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "data.akshare_client.ak.stock_zh_a_hist",
            lambda **kwargs: pd.DataFrame(),
        )
        client = AkShareClientV36(cache_dir=str(tmp_path))
        with pytest.raises(RuntimeError, match="没有返回历史数据"):
            client.get_daily("000001", "20240101", "20240105")

    def test_get_daily_exception_raises(self, monkeypatch, tmp_path):
        def boom(**kwargs):
            raise ConnectionError("network down")

        monkeypatch.setattr("data.akshare_client.ak.stock_zh_a_hist", boom)
        client = AkShareClientV36(cache_dir=str(tmp_path))
        with pytest.raises(RuntimeError, match="AkShare 获取000001历史数据失败"):
            client.get_daily("000001", "20240101", "20240105")


# ---------------------------------------------------------------
# PriceLoader
# ---------------------------------------------------------------


class TestPriceLoader:
    def test_load_standardizes(self, monkeypatch):
        df_in = pd.DataFrame(
            {
                "日期": ["2024-01-03", "2024-01-02", "2024-01-02"],
                "开盘": ["10.0", "9.5", "9.5"],
                "收盘": ["10.5", "9.8", "9.8"],
                "最高": ["10.8", "9.9", "9.9"],
                "最低": ["9.9", "9.4", "9.4"],
                "成交量": ["1000", "900", "900"],
                "成交额": ["10000", "9000", "9000"],
            }
        )
        monkeypatch.setattr(
            "data.akshare_client.AkShareClientV36.get_daily",
            lambda self, code, start_date, end_date, adjust="qfq": df_in,
        )
        loader = PriceLoader()
        df = loader.load("000001", "20240101", "20240105")
        # 排序 + 去重
        assert list(df["日期"]) == list(pd.to_datetime(["2024-01-02", "2024-01-03"]))
        # 数值化
        assert df["开盘"].dtype.kind == "f"
        assert df["成交量"].dtype.kind in "if"

    def test_load_missing_columns_raises(self, monkeypatch):
        df_in = pd.DataFrame({"日期": ["2024-01-02"], "收盘": [10.0]})
        monkeypatch.setattr(
            "data.akshare_client.AkShareClientV36.get_daily",
            lambda self, code, start_date, end_date, adjust="qfq": df_in,
        )
        loader = PriceLoader()
        with pytest.raises(ValueError, match="缺少字段"):
            loader.load("000001", "20240101", "20240105")


# ---------------------------------------------------------------
# TradingCalendar
# ---------------------------------------------------------------


class TestTradingCalendar:
    def test_business_days(self):
        days = TradingCalendar.business_days("2024-01-01", "2024-01-05")
        # 2024-01-01 周一；01-01 元旦，但 bdate_range 只排除周末
        assert len(days) >= 4

    def test_is_trading_day(self):
        days = TradingCalendar.business_days("2024-01-01", "2024-01-05")
        assert TradingCalendar.is_trading_day("2024-01-02", days) is True
        assert TradingCalendar.is_trading_day("2024-01-06", days) is False  # 周六


# ---------------------------------------------------------------
# LimitRule
# ---------------------------------------------------------------


class TestLimitRule:
    def test_limit_pct_by_board(self):
        rule = LimitRule()
        assert rule.limit_pct("600000") == 0.10
        assert rule.limit_pct("000001") == 0.10
        assert rule.limit_pct("300394") == 0.20
        assert rule.limit_pct("688001") == 0.20
        assert rule.limit_pct("430047") == 0.30
        assert rule.limit_pct("830799") == 0.30
        assert rule.limit_pct("870299") == 0.30
        assert rule.limit_pct("900901") == 0.10  # 其他默认 10%

    def test_is_limit_up_down(self):
        rule = LimitRule()
        prev = 10.0
        # 主板涨停价 10*(1+0.10-0.002)=10.98，>= 10.98 判涨停
        assert rule.is_limit_up(prev, 11.0, "600000") is True
        assert rule.is_limit_up(prev, 10.98, "600000") is True
        assert rule.is_limit_up(prev, 10.97, "600000") is False
        # 主板跌停价 10*(1-0.10+0.002)=9.02，<= 9.02 判跌停
        assert rule.is_limit_down(prev, 9.0, "600000") is True
        assert rule.is_limit_down(prev, 9.02, "600000") is True
        assert rule.is_limit_down(prev, 9.03, "600000") is False
        # prev_close <= 0
        assert rule.is_limit_up(0.0, 10.0, "600000") is False
        assert rule.is_limit_down(0.0, 10.0, "600000") is False


# ---------------------------------------------------------------
# SuspensionDetector
# ---------------------------------------------------------------


class TestSuspensionDetector:
    def test_normal_not_suspended(self):
        row = pd.Series({"收盘": 10.0, "成交量": 1000})
        assert SuspensionDetector.is_suspended(row) is False

    def test_none_suspended(self):
        assert SuspensionDetector.is_suspended(None) is True

    def test_nan_close_suspended(self):
        row = pd.Series({"收盘": float("nan"), "成交量": 1000})
        assert SuspensionDetector.is_suspended(row) is True

    def test_nan_volume_suspended(self):
        row = pd.Series({"收盘": 10.0, "成交量": float("nan")})
        assert SuspensionDetector.is_suspended(row) is True

    def test_zero_volume_suspended(self):
        row = pd.Series({"收盘": 10.0, "成交量": 0})
        assert SuspensionDetector.is_suspended(row) is True


# ---------------------------------------------------------------
# AShareTradingRules (T+1)
# ---------------------------------------------------------------


class TestAShareTradingRules:
    def test_t1_sellable(self):
        rules = AShareTradingRules()
        rules.record_buy("000001", 500, "2024-01-02")
        # 当天买入的不可卖
        assert rules.sellable_shares("000001", 500, "2024-01-02") == 0
        # 次日可卖
        assert rules.sellable_shares("000001", 500, "2024-01-03") == 500

    def test_t1_partial(self):
        rules = AShareTradingRules()
        rules.record_buy("000001", 300, "2024-01-02")
        assert rules.sellable_shares("000001", 800, "2024-01-02") == 500
        assert rules.sellable_shares("000001", 800, "2024-01-03") == 800

    def test_t1_no_negative(self):
        rules = AShareTradingRules()
        rules.record_buy("000001", 500, "2024-01-02")
        assert rules.sellable_shares("000001", 200, "2024-01-02") == 0


# ---------------------------------------------------------------
# TradingCostModel
# ---------------------------------------------------------------


class TestTradingCostModel:
    def test_commission_minimum(self):
        model = TradingCostModel()
        assert model.commission(1000) == 5.0  # 1000*0.0003=0.3 < 5
        assert model.commission(0) == 0.0

    def test_commission_rate(self):
        model = TradingCostModel()
        assert model.commission(100000) == pytest.approx(30.0)

    def test_stamp_duty(self):
        model = TradingCostModel()
        assert model.stamp_duty(100000) == pytest.approx(50.0)
        assert model.stamp_duty(0) == 0.0

    def test_slippage(self):
        model = TradingCostModel()
        assert model.buy_price(10.0) == pytest.approx(10.005)
        assert model.sell_price(10.0) == pytest.approx(9.995)


# ---------------------------------------------------------------
# ExecutionEngine
# ---------------------------------------------------------------


class TestExecutionEngine:
    def test_buy_success(self):
        engine = ExecutionEngine(TradingCostModel())
        r = engine.buy(cash=100000, price=10.0, target_value=50000)
        assert r.executed is True
        assert r.reason == "BUY"
        assert r.shares > 0 and r.shares % 100 == 0
        assert r.cash_change < 0

    def test_buy_limit_up_rejected(self):
        engine = ExecutionEngine(TradingCostModel())
        r = engine.buy(cash=100000, price=10.0, target_value=50000, limit_up=True)
        assert r.executed is False
        assert r.reason == "LIMIT_UP"
        assert r.shares == 0

    def test_buy_insufficient_value(self):
        engine = ExecutionEngine(TradingCostModel())
        r = engine.buy(cash=100000, price=10.0, target_value=10)
        assert r.executed is False
        assert r.reason == "INSUFFICIENT_VALUE"

    def test_buy_no_cash(self):
        engine = ExecutionEngine(TradingCostModel())
        r = engine.buy(cash=0.5, price=10.0, target_value=50000)
        assert r.executed is False
        assert r.reason == "NO_CASH"

    def test_buy_cash_shrink(self):
        # 现金不足以买入目标价值 → 折算到现金内
        engine = ExecutionEngine(TradingCostModel())
        r = engine.buy(cash=5000, price=10.0, target_value=50000)
        assert r.executed is True
        assert r.shares > 0 and r.shares % 100 == 0
        assert r.cash_change >= -5000

    def test_sell_success(self):
        engine = ExecutionEngine(TradingCostModel())
        r = engine.sell(shares=1000, price=10.0)
        assert r.executed is True
        assert r.reason == "SELL"
        assert r.stamp_duty > 0
        assert r.fee > 0
        assert r.cash_change > 0

    def test_sell_no_position(self):
        engine = ExecutionEngine(TradingCostModel())
        r = engine.sell(shares=0, price=10.0)
        assert r.executed is False
        assert r.reason == "NO_POSITION"

    def test_sell_limit_down_rejected(self):
        engine = ExecutionEngine(TradingCostModel())
        r = engine.sell(shares=1000, price=10.0, limit_down=True)
        assert r.executed is False
        assert r.reason == "LIMIT_DOWN"


# ---------------------------------------------------------------
# DataQualityChecker
# ---------------------------------------------------------------


def make_df(rows=None, dates=None):
    if rows is None:
        rows = [
            {"日期": "2024-01-02", "开盘": 10.0, "收盘": 10.5, "最高": 10.8, "最低": 9.9},
            {"日期": "2024-01-03", "开盘": 10.5, "收盘": 10.8, "最高": 11.0, "最低": 10.4},
        ]
    df = pd.DataFrame(rows)
    df["日期"] = pd.to_datetime(df["日期"])
    return df


class TestDataQualityChecker:
    def test_valid(self):
        checker = DataQualityChecker()
        result = checker.check(make_df())
        assert result["valid"] is True
        assert result["issues"] == []
        assert result["rows"] == 2
        assert result["start"] == "2024-01-02 00:00:00"
        assert result["end"] == "2024-01-03 00:00:00"

    def test_empty(self):
        checker = DataQualityChecker()
        result = checker.check(pd.DataFrame(columns=["日期"]))
        assert result["valid"] is False
        assert "EMPTY_DATA" in result["issues"]

    def test_date_not_sorted(self):
        checker = DataQualityChecker()
        df = make_df()
        df = df.iloc[::-1].reset_index(drop=True)
        result = checker.check(df)
        assert "DATE_NOT_SORTED" in result["issues"]

    def test_duplicate_dates(self):
        checker = DataQualityChecker()
        df = pd.concat([make_df(), make_df()], ignore_index=True)
        result = checker.check(df)
        assert "DUPLICATE_DATES" in result["issues"]

    def test_invalid_price(self):
        checker = DataQualityChecker()
        df = make_df()
        df.loc[0, "收盘"] = 0.0
        result = checker.check(df)
        assert "INVALID_收盘" in result["issues"]

    def test_high_low_error(self):
        checker = DataQualityChecker()
        df = make_df()
        df.loc[0, "最高"] = 9.0  # < 最低 9.9
        result = checker.check(df)
        assert "HIGH_LOW_ERROR" in result["issues"]
