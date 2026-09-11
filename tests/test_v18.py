"""V1.8 真实市场强化学习训练平台 单元测试。"""

import numpy as np
import pandas as pd
import pytest

from data_engine.akshare_loader import AkShareLoader
from dataset.stock_dataset import StockDataset
from dataset.feature_pipeline import FeaturePipeline
from rl.multi_stock_env import MultiStockEnvironment
from rl.transaction_cost import TransactionCost
from rl.slippage import SlippageModel
from backtest.walk_forward import WalkForward
from backtest.performance import Performance
from evolution.model_rank import ModelRank


def _make_df(n=60, seed=7):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "close": close,
            "volume": rng.integers(1_000_000, 5_000_000, n).astype(float),
            "high": close * 1.01,
            "low": close * 0.99,
        }
    )


class TestAkShareLoader:
    def test_load_daily_renames_columns(self, monkeypatch):
        df = _make_df()
        raw = df.rename(
            columns={
                "date": "日期",
                "close": "收盘",
                "volume": "成交量",
                "high": "最高",
                "low": "最低",
            }
        )

        class FakeAk:
            @staticmethod
            def stock_zh_a_hist(symbol, period, adjust):
                return raw

        monkeypatch.setattr("data_engine.akshare_loader.ak", FakeAk())
        loader = AkShareLoader()
        out = loader.load_daily("600519")
        assert list(out.columns) == ["date", "close", "volume", "high", "low"]
        assert len(out) == 60

    def test_load_batch_continues_on_error(self, monkeypatch):
        class FakeAk:
            @staticmethod
            def stock_zh_a_hist(symbol, period, adjust):
                if symbol == "BAD":
                    raise RuntimeError("limit")
                return _make_df()

        monkeypatch.setattr("data_engine.akshare_loader.ak", FakeAk())
        loader = AkShareLoader()
        result = loader.load_batch(["600519", "BAD", "300394"])
        assert "600519" in result and "300394" in result
        assert "BAD" not in result


class TestStockDataset:
    def test_merge_adds_code_column(self):
        ds = StockDataset({"600519": _make_df(10), "300394": _make_df(12)})
        merged = ds.merge()
        assert set(merged["code"]) == {"600519", "300394"}
        assert len(merged) == 22


class TestFeaturePipeline:
    def test_transform_columns_and_length(self):
        out = FeaturePipeline().transform(_make_df(60))
        for col in ["return_1", "ma5", "ma20", "volume_change", "momentum"]:
            assert col in out.columns
        assert len(out) < 60  # dropna 后减少

    def test_transform_no_nan(self):
        out = FeaturePipeline().transform(_make_df(80))
        assert out[["return_1", "ma5", "ma20", "volume_change", "momentum"]].notna().all().all()


class TestMultiStockEnvironment:
    def test_reset_state(self):
        env = MultiStockEnvironment(_make_df(30))
        s = env.reset()
        assert s["cash"] == 1_000_000
        assert s["positions"] == {}
        assert s["day"] == 0

    def test_step_buy_sell(self):
        env = MultiStockEnvironment(_make_df(30))
        env.reset()
        nxt, reward, done = env.step({"code": "600519", "type": "BUY"})
        assert nxt["positions"] == {"600519": 1}
        assert reward == 0
        nxt, _, _ = env.step({"code": "600519", "type": "SELL"})
        assert "600519" not in nxt["positions"]

    def test_step_done_at_end(self):
        env = MultiStockEnvironment(_make_df(5))
        env.reset()
        for _ in range(4):
            _, _, done = env.step({"code": "600519", "type": "BUY"})
        assert done is True


class TestTransactionCost:
    def test_commission_floor(self):
        cost = TransactionCost().calculate(10_000)
        assert cost == 5 + 10  # 佣金 5 元下限 + 印花税 10 元

    def test_commission_percent(self):
        cost = TransactionCost().calculate(1_000_000)
        assert cost == pytest.approx(300 + 1000)


class TestSlippageModel:
    def test_apply(self):
        assert SlippageModel().apply(100, 1000) == pytest.approx(100.05)


class TestWalkForward:
    def test_split_ratio(self):
        train, test = WalkForward().split(list(range(100)), 0.7)
        assert len(train) == 70 and len(test) == 30

    def test_split_default(self):
        train, test = WalkForward().split(list(range(10)))
        assert len(train) == 7 and len(test) == 3


class TestPerformance:
    def test_analyze_up_trend(self):
        res = Performance().analyze([1.0, 1.05, 1.10, 1.15])
        assert res["return"] == pytest.approx(0.15)
        assert res["sharpe"] > 0
        assert res["max_drawdown"] == pytest.approx(0.0)

    def test_analyze_drawdown(self):
        res = Performance().analyze([1.0, 1.2, 0.9, 1.0])
        assert res["max_drawdown"] < -0.2


class TestModelRank:
    def test_ranking_sorted(self):
        rank = ModelRank()
        rank.add("A", {"sharpe": 1.0})
        rank.add("B", {"sharpe": 2.5})
        rank.add("C", {"sharpe": 0.5})
        names = [m["name"] for m in rank.ranking()]
        assert names == ["B", "A", "C"]
