# -*- coding: utf-8 -*-
"""V3.0.1 - V3.0.6 测试。

覆盖：
- V3.0.1 Real Market Data Engine（schemas / cache / market_data）
- V3.0.2 5000 A 股自动扫描（universe / StockScannerV302 / MarketScanner）
- V3.0.3 自动投资流水线（InvestmentPipeline 报告结构与保存）
- V3.0.4 Paper Trading 账本（TradeLedger / PaperBroker ledger / AccountReport）
- V3.0.5 AI Trade Review（TradeReviewV305 / ReviewEngine / TradeReviewAgent）
- V3.0.6 策略健康与淘汰（StrategyHealth / StrategyRetirementEngine / EvolutionController / main_v306）
"""
import os
import tempfile

import pandas as pd
import pytest


@pytest.fixture()
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ---------------------------------------------------------------
# V3.0.1 Real Market Data Engine
# ---------------------------------------------------------------
class TestV301Schemas:
    def test_stock_quote_defaults(self):
        from data.schemas import StockQuote

        q = StockQuote(code="600519", name="贵州茅台")
        assert q.latest_price is None
        assert q.pe is None
        d = q.to_dict()
        assert d["code"] == "600519"
        assert d["name"] == "贵州茅台"
        assert "market_cap" in d

    def test_stock_quote_fields(self):
        from data.schemas import StockQuote

        q = StockQuote(
            code="000001",
            name="平安银行",
            latest_price=12.5,
            change_pct=1.2,
            market_cap=3.0e11,
        )
        assert q.latest_price == 12.5
        assert q.to_dict()["change_pct"] == 1.2


class TestV301Cache:
    def test_set_get(self, tmp_dir):
        from data.cache import DataCache

        cache = DataCache(
            directory=os.path.join(tmp_dir, "cache"),
            ttl_seconds=60,
        )
        cache.set("quote_600519", {"code": "600519"})
        assert cache.get("quote_600519") == {"code": "600519"}

    def test_missing_and_expired(self, tmp_dir):
        import time

        from data.cache import DataCache

        cache = DataCache(
            directory=os.path.join(tmp_dir, "cache"),
            ttl_seconds=1,
        )
        assert cache.get("nope") is None
        cache.set("k", {"v": 1})
        time.sleep(1.2)
        assert cache.get("k") is None

    def test_bad_json_returns_none(self, tmp_dir):
        from data.cache import DataCache

        cache = DataCache(
            directory=os.path.join(tmp_dir, "cache"),
            ttl_seconds=60,
        )
        p = cache._path("bad")
        p.write_text("{not json", encoding="utf-8")
        assert cache.get("bad") is None


class TestV301MarketData:
    def test_normalize_code(self):
        from data.market_data import MarketData

        assert MarketData.normalize_code("600519") == "600519"
        assert MarketData.normalize_code("sh600519") == "600519"
        assert MarketData.normalize_code("SZ000001") == "000001"
        assert MarketData.normalize_code("bj430047") == "430047"
        with pytest.raises(ValueError):
            MarketData.normalize_code("60051")
        with pytest.raises(ValueError):
            MarketData.normalize_code("abc123")

    def test_float_conversion(self):
        from data.market_data import MarketData

        assert MarketData._float(None) is None
        assert MarketData._float("1.5") == 1.5
        assert MarketData._float(3) == 3.0
        assert MarketData._float("abc") is None

    def test_market_data_error_type(self):
        from data.market_data import MarketDataError

        assert issubclass(MarketDataError, RuntimeError)


# ---------------------------------------------------------------
# V3.0.2 5000 A 股自动扫描
# ---------------------------------------------------------------
def _sample_df():
    return pd.DataFrame(
        {
            "代码": ["600519", "000001", "000002", "300001"],
            "名称": ["贵州茅台", "平安银行", "*ST测试", "特锐德"],
            "最新价": [1800.0, 12.0, 0.0, 25.0],
            "总市值": [2.2e12, 3.0e11, 5.0e8, 4.0e9],
            "市盈率-动态": [30.0, 6.0, None, 150.0],
            "换手率": [1.2, 0.8, 0.1, 2.0],
            "涨跌幅": [3.5, 1.0, -2.0, 5.0],
        }
    )


class TestV302Universe:
    def test_clean_filters_st_and_zero_price(self):
        from scanner.universe import AShareUniverse

        df = _sample_df()
        clean = AShareUniverse().clean(df)
        codes = set(clean["代码"])
        # 排除 *ST 与 最新价=0
        assert "000002" not in codes
        assert len(clean) == 3

    def test_clean_preserves_normal(self):
        from scanner.universe import AShareUniverse

        clean = AShareUniverse().clean(_sample_df())
        assert "600519" in set(clean["代码"])
        assert "000001" in set(clean["代码"])


class TestV302StockScanner:
    def test_scan_dataframe(self):
        from scanner.stock_scanner import StockScannerV302

        scanner = StockScannerV302()
        result = scanner.scan_dataframe(_sample_df(), limit=100)
        # 600519 与 000001 通过（市值/PE/换手），000002/300001 被过滤
        assert len(result) == 2
        assert result[0]["code"] == "600519"  # 涨跌幅最大排前
        assert result[1]["code"] == "000001"
        assert result[0]["pe_dynamic"] == 30.0
        assert result[0]["market_cap"] == 2.2e12

    def test_scan_dataframe_limit(self):
        from scanner.stock_scanner import StockScannerV302

        scanner = StockScannerV302()
        result = scanner.scan_dataframe(_sample_df(), limit=1)
        assert len(result) == 1
        assert result[0]["code"] == "600519"

    def test_scan_empty_df(self):
        from scanner.stock_scanner import StockScannerV302

        assert StockScannerV302().scan_dataframe(pd.DataFrame()) == []

    def test_scan_star_st_keyword_regex(self):
        """回归：*ST 关键词不能使正则编译失败。"""
        from scanner.universe import AShareUniverse

        df = pd.DataFrame(
            {
                "代码": ["000002"],
                "名称": ["*ST测试"],
                "最新价": [5.0],
            }
        )
        clean = AShareUniverse().clean(df)
        assert clean.empty


class TestV302MarketScanner:
    def test_imports(self):
        from scanner.market_scanner import MarketScanner

        ms = MarketScanner()
        assert ms.scanner is not None
        assert ms.data is not None


# ---------------------------------------------------------------
# V3.0.3 自动投资流水线
# ---------------------------------------------------------------
class TestV303Pipeline:
    def test_save_report_writes_json(self, tmp_dir):
        from pipeline.investment_pipeline import InvestmentPipeline

        report = {
            "timestamp": "2026-09-13T10:00:00",
            "candidate_count": 0,
            "decisions": [],
            "targets": [],
            "risk": {"valid": True},
        }
        path = InvestmentPipeline.save_report(
            report,
            directory=os.path.join(tmp_dir, "reports"),
        )
        assert os.path.exists(path)
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["candidate_count"] == 0
        assert data["risk"] == {"valid": True}

    def test_run_signature(self):
        import inspect

        from pipeline.investment_pipeline import InvestmentPipeline

        sig = inspect.signature(InvestmentPipeline.run)
        assert "scan_limit" in sig.parameters


# ---------------------------------------------------------------
# V3.0.4 Paper Trading 完整账本
# ---------------------------------------------------------------
class TestV304Ledger:
    def test_append_and_persist(self, tmp_dir):
        from trading.ledger import TradeLedger

        path = os.path.join(tmp_dir, "ledger.json")
        ledger = TradeLedger(path=path)
        ledger.append({"code": "600519", "side": "buy", "quantity": 100})
        ledger.append({"code": "000001", "side": "sell", "quantity": 50})
        assert len(ledger.all()) == 2
        assert ledger.all()[0]["trade_id"] == "T00000001"
        assert ledger.all()[1]["trade_id"] == "T00000002"
        assert "timestamp" in ledger.all()[0]

        # 重新加载验证持久化
        ledger2 = TradeLedger(path=path)
        assert len(ledger2.all()) == 2

    def test_last_n(self, tmp_dir):
        from trading.ledger import TradeLedger

        ledger = TradeLedger(path=os.path.join(tmp_dir, "ledger.json"))
        for i in range(5):
            ledger.append({"code": str(i)})
        last = ledger.last(2)
        assert [t["code"] for t in last] == ["3", "4"]
        assert ledger.last(100) == ledger.all()

    def test_corrupt_file_returns_empty(self, tmp_dir):
        from trading.ledger import TradeLedger

        path = os.path.join(tmp_dir, "ledger.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("corrupt")
        assert TradeLedger(path=path).all() == []


class TestV304PaperBrokerLedger:
    def test_fill_appends_ledger(self, tmp_dir):
        from portfolio.portfolio import PortfolioV30
        from trading.ledger import TradeLedger
        from trading.order import OrderSideV30
        from trading.paper_broker import PaperBrokerV30

        ledger = TradeLedger(path=os.path.join(tmp_dir, "pb.json"))
        broker = PaperBrokerV30(
            portfolio=PortfolioV30(initial_cash=1_000_000),
            ledger=ledger,
        )
        order = broker.submit_order(
            "600519", "贵州茅台", OrderSideV30.BUY, 100, 1800.0
        )
        assert order.status == "FILLED"
        trades = ledger.all()
        assert len(trades) == 1
        assert trades[0]["code"] == "600519"
        assert trades[0]["side"] == "BUY"
        assert trades[0]["commission"] == 0.0003
        assert trades[0]["slippage"] == 0.0005

    def test_reject_does_not_append(self, tmp_dir):
        from portfolio.portfolio import PortfolioV30
        from trading.ledger import TradeLedger
        from trading.order import OrderSideV30
        from trading.paper_broker import PaperBrokerV30

        ledger = TradeLedger(path=os.path.join(tmp_dir, "pb2.json"))
        broker = PaperBrokerV30(
            portfolio=PortfolioV30(initial_cash=1_000_000),
            ledger=ledger,
        )
        order = broker.submit_order(
            "600519", "贵州茅台", OrderSideV30.BUY, 99999999, 99999.0
        )
        assert order.status == "REJECTED"
        assert ledger.all() == []


class TestV304AccountReport:
    def test_generate_empty_portfolio(self):
        from portfolio.portfolio import PortfolioV30
        from trading.account_report import AccountReport

        portfolio = PortfolioV30(initial_cash=1_000_000)
        report = AccountReport().generate(portfolio)
        assert report["cash"] == 1_000_000
        assert report["market_value"] == 0
        assert report["total_value"] == 1_000_000
        assert report["positions"] == []
        assert report["trade_count"] == 0

    def test_generate_with_position(self):
        from portfolio.portfolio import PortfolioV30
        from trading.account_report import AccountReport

        portfolio = PortfolioV30(initial_cash=1_000_000)
        portfolio.positions["600519"] = type(
            "Pos",
            (),
            {
                "code": "600519",
                "name": "贵州茅台",
                "shares": 100,
                "avg_price": 1800.0,
                "current_price": 1800.0,
                "market_value": 180000.0,
                "pnl": 0.0,
                "pnl_pct": 0.0,
            },
        )()
        report = AccountReport().generate(portfolio)
        assert report["market_value"] == 180000.0
        assert report["positions"][0]["code"] == "600519"


# ---------------------------------------------------------------
# V3.0.5 AI Trade Review
# ---------------------------------------------------------------
class TestV305TradeReview:
    def _make(self):
        from review.trade_review import TradeReviewV305

        return TradeReviewV305()

    def test_excellent(self):
        r = self._make().review({"pnl_pct": 0.15, "holding_days": 5})
        assert r["result"] == "EXCELLENT"
        assert r["review_score"] == 80
        assert "该交易收益明显高于基础阈值" in r["lessons"]

    def test_win(self):
        r = self._make().review({"pnl_pct": 0.05, "holding_days": 5})
        assert r["result"] == "WIN"
        assert r["review_score"] == 60

    def test_bad_loss(self):
        r = self._make().review({"pnl_pct": -0.15, "holding_days": 5})
        assert r["result"] == "BAD_LOSS"
        assert r["review_score"] == 20

    def test_loss(self):
        r = self._make().review({"pnl_pct": -0.05, "holding_days": 2})
        assert r["result"] == "LOSS"
        assert r["review_score"] == 40
        assert "属于短周期交易" in r["lessons"]

    def test_long_holding_penalty(self):
        r = self._make().review({"pnl_pct": 0.05, "holding_days": 61})
        assert r["review_score"] == 55
        assert "持仓周期较长" in r["lessons"]

    def test_score_clamped(self):
        r = self._make().review({"pnl_pct": -0.15, "holding_days": 70})
        assert r["review_score"] == 15  # 50 - 30 - 5
        r = self._make().review({"pnl_pct": -0.9, "holding_days": 90})
        assert r["review_score"] == 15  # 50-30-5，无更多扣分项
        r = self._make().review({"pnl_pct": 0.9, "holding_days": 1})
        assert r["review_score"] == 80  # 50+30，短周期只加 lesson 不加分

    def test_batch_review_empty(self):
        assert self._make().batch_review([]) == []


class TestV305ReviewEngine:
    def test_empty(self):
        from review.review_engine import ReviewEngine

        stats = ReviewEngine().analyze([])
        assert stats == {"count": 0, "win_rate": 0, "avg_pnl": 0, "avg_score": 0}

    def test_stats(self):
        from review.review_engine import ReviewEngine
        from review.trade_review import TradeReviewV305

        tr = TradeReviewV305()
        reviews = [
            tr.review({"pnl_pct": 0.15, "holding_days": 5}),
            tr.review({"pnl_pct": -0.05, "holding_days": 2}),
            tr.review({"pnl_pct": 0.05, "holding_days": 5}),
            tr.review({"pnl_pct": -0.15, "holding_days": 5}),
        ]
        stats = ReviewEngine().analyze(reviews)
        assert stats["count"] == 4
        assert stats["win_rate"] == 0.5
        assert stats["avg_score"] == (80 + 40 + 60 + 20) / 4


class TestV305TradeReviewAgent:
    def test_no_key_raises(self, monkeypatch):
        import agents.trade_review_agent as mod

        class FakeSettings:
            openai_api_key = ""
            openai_model = "gpt-4o-mini"

        # agent 模块内通过 from-import 绑定了 get_settings，需 patch 模块级名字
        monkeypatch.setattr(mod, "get_settings", lambda: FakeSettings())
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            mod.TradeReviewAgent()

    def test_import_ok(self):
        import agents.trade_review_agent  # noqa: F401


# ---------------------------------------------------------------
# V3.0.6 AI 自动淘汰策略
# ---------------------------------------------------------------
class TestV306StrategyHealth:
    def test_healthy(self):
        from strategy_lab.strategy_health import StrategyHealth

        r = StrategyHealth().evaluate(
            {"sharpe": 1.0, "max_drawdown": -0.10, "win_rate": 0.5, "total_return": 0.2}
        )
        assert r["status"] == "HEALTHY"
        assert r["health_score"] == 100
        assert r["reasons"] == []

    def test_watch(self):
        from strategy_lab.strategy_health import StrategyHealth

        r = StrategyHealth().evaluate(
            {"sharpe": 0.4, "max_drawdown": -0.25, "win_rate": 0.5, "total_return": 0.1}
        )
        assert r["status"] == "WATCH"
        assert r["health_score"] == 65

    def test_underperform(self):
        from strategy_lab.strategy_health import StrategyHealth

        r = StrategyHealth().evaluate(
            {"sharpe": 0.2, "max_drawdown": -0.22, "win_rate": 0.3, "total_return": 0.1}
        )
        assert r["status"] == "UNDERPERFORM"
        assert r["health_score"] == 50

    def test_retired(self):
        from strategy_lab.strategy_health import StrategyHealth

        r = StrategyHealth().evaluate(
            {"sharpe": -0.5, "max_drawdown": -0.35, "win_rate": 0.3, "total_return": -0.1}
        )
        assert r["status"] == "RETIRED"
        assert r["health_score"] == 0

    def test_score_boundaries(self):
        from strategy_lab.strategy_health import StrategyHealth

        sh = StrategyHealth()
        # sharpe<0 → -30：100-30=70 → WATCH
        assert sh.evaluate({"sharpe": -1.0, "max_drawdown": -0.10, "win_rate": 0.5, "total_return": 0.0})["status"] == "WATCH"
        # 35 → RETIRED：sharpe -0.5(-30) + win_rate 0.3(-15) + total_return -0.1(-20)
        r = sh.evaluate({"sharpe": -0.5, "max_drawdown": 0.0, "win_rate": 0.3, "total_return": -0.1})
        assert r["health_score"] == 35 and r["status"] == "RETIRED"


class TestV306Retirement:
    def test_should_retire(self):
        from strategy_lab.retirement import StrategyRetirementEngine

        engine = StrategyRetirementEngine()
        assert not engine.should_retire(
            {"max_drawdown": -0.10, "sharpe": 1.0},
            {"health_score": 90},
        )
        assert engine.should_retire(
            {"max_drawdown": -0.10, "sharpe": 1.0},
            {"health_score": 30},
        )
        assert engine.should_retire(
            {"max_drawdown": -0.50, "sharpe": 1.0},
            {"health_score": 90},
        )
        assert engine.should_retire(
            {"max_drawdown": -0.10, "sharpe": -0.1},
            {"health_score": 90},
        )

    def test_process_updates_status(self):
        from strategy_lab.retirement import StrategyRetirementEngine

        class FakeStrategy:
            def __init__(self, metrics):
                self.metrics = metrics
                self.status = "EXPERIMENT"

        engine = StrategyRetirementEngine()
        s, health = engine.process(
            FakeStrategy({"sharpe": 1.0, "max_drawdown": -0.10, "win_rate": 0.5, "total_return": 0.2})
        )
        assert s.status == "HEALTHY"
        s2, _ = engine.process(
            FakeStrategy({"sharpe": -1.0, "max_drawdown": -0.50, "win_rate": 0.2, "total_return": -0.3})
        )
        assert s2.status == "RETIRED"


class TestV306EvolutionController:
    def test_evolve_population_size(self):
        from evolution.evolution_controller import EvolutionController
        from evolution.genetic_algorithm import GeneticAlgorithmV281
        from evolution.strategy_generator import StrategyGeneratorV281

        gen = StrategyGeneratorV281()
        ctrl = EvolutionController(gen, GeneticAlgorithmV281())
        pop = gen.generate_population(20)
        for i, s in enumerate(pop):
            s.metrics = {"score": 100 - i}
            s.status = "HEALTHY" if i < 15 else "RETIRED"
        new_pop = ctrl.evolve(pop, population_size=50)
        assert len(new_pop) == 50

    def test_evolve_refills_small_population(self):
        from evolution.evolution_controller import EvolutionController
        from evolution.genetic_algorithm import GeneticAlgorithmV281
        from evolution.strategy_generator import StrategyGeneratorV281

        gen = StrategyGeneratorV281()
        ctrl = EvolutionController(gen, GeneticAlgorithmV281())
        pop = gen.generate_population(5)
        for s in pop:
            s.status = "RETIRED"
        new_pop = ctrl.evolve(pop, population_size=30)
        assert len(new_pop) == 30


class TestV306Main:
    def test_main_runs(self, capsys):
        import main_v306

        main_v306.main()
        out = capsys.readouterr().out
        assert "AI HEDGE FUND OS V3.0.6" in out
        assert "V3.0.6 COMPLETE" in out
        assert "New Population: 100" in out
