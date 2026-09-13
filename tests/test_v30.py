"""V3.0 AI Autonomous Hedge Fund（第一个闭环版本）单元测试。"""

import pytest

from scanner.stock_scanner import StockScannerV30
from portfolio.position import PositionV30
from portfolio.portfolio import PortfolioV30
from portfolio.portfolio_manager import PortfolioManagerV30
from risk.risk_engine import RiskEngineV30
from trading.order import OrderSideV30, OrderV30
from trading.paper_broker import PaperBrokerV30
from trading.execution_engine import ExecutionEngineV30
from review.trade_review import TradeReviewV30


class TestStockScannerV30:
    def test_filter(self):
        s = StockScannerV30()
        assert s.filter_stock({"market_cap": 1e10, "pe_dynamic": 30, "turnover_pct": 2})
        assert not s.filter_stock({"market_cap": 1e8, "pe_dynamic": 30, "turnover_pct": 2})
        assert not s.filter_stock({"market_cap": 1e10, "pe_dynamic": 200, "turnover_pct": 2})
        assert not s.filter_stock({"market_cap": 1e10, "pe_dynamic": 30, "turnover_pct": 0.1})

    def test_scan_limit(self):
        s = StockScannerV30()
        stocks = [
            {"code": "A", "change_pct": 1, "market_cap": 1e10, "pe_dynamic": 20, "turnover_pct": 1},
            {"code": "B", "change_pct": 3, "market_cap": 1e10, "pe_dynamic": 20, "turnover_pct": 1},
            {"code": "C", "change_pct": 2, "market_cap": 1e10, "pe_dynamic": 20, "turnover_pct": 1},
        ]
        r = s.scan(stocks, limit=2)
        assert [x["code"] for x in r] == ["B", "C"]


class TestPositionV30:
    def test_props(self):
        p = PositionV30(code="300394", name="x", shares=100, avg_price=10.0, current_price=12.0)
        assert p.market_value == 1200.0
        assert p.pnl == 200.0
        assert p.pnl_pct == pytest.approx(0.2)

    def test_pnl_pct_zero_price(self):
        p = PositionV30(code="300394", name="x")
        assert p.pnl_pct == 0.0


class TestPortfolioV30:
    def test_basic(self):
        pf = PortfolioV30(initial_cash=1_000_000)
        assert pf.total_value == 1_000_000
        assert pf.pnl == 0.0
        pf.add_position(PositionV30(code="300394", name="x", shares=100, avg_price=10.0, current_price=12.0))
        assert pf.market_value == 1200.0
        pf.update_prices({"300394": 15.0})
        assert pf.market_value == 1500.0
        pf.remove_position("300394")
        assert len(pf.positions) == 0

    def test_snapshot(self):
        pf = PortfolioV30()
        snap = pf.snapshot()
        assert snap["cash"] == 1_000_000
        assert snap["return_pct"] == 0.0


class TestPortfolioManagerV30:
    def test_build_targets(self):
        pm = PortfolioManagerV30(max_positions=2, max_single_weight=0.20)
        decisions = [
            {"code": "A", "decision": "BUY", "weighted_score": 3.0},
            {"code": "B", "decision": "BUY", "weighted_score": 2.5},
            {"code": "C", "decision": "HOLD", "weighted_score": 1.0},
        ]
        targets = pm.build_targets(decisions)
        assert [t["code"] for t in targets] == ["A", "B"]
        assert targets[0]["target_weight"] == pytest.approx(0.20)

    def test_no_buys(self):
        pm = PortfolioManagerV30()
        assert pm.build_targets([{"code": "A", "decision": "HOLD"}]) == []


class TestRiskEngineV30:
    def test_validate_position(self):
        r = RiskEngineV30()
        assert r.validate_position(0.1)["allowed"]
        assert not r.validate_position(0.3)["allowed"]
        assert not r.validate_position(-0.1)["allowed"]

    def test_validate_portfolio(self):
        r = RiskEngineV30()
        assert r.validate_portfolio({"A": 0.1, "B": 0.1})["allowed"]
        assert not r.validate_portfolio({"A": 0.6, "B": 0.6})["allowed"]


class TestPaperBrokerV30:
    def test_buy(self):
        pf = PortfolioV30(initial_cash=100_000)
        b = PaperBrokerV30(portfolio=pf)
        o = b.submit_order("300394", "示例", OrderSideV30.BUY, 100, 100.0)
        assert o.status == "FILLED"
        assert pf.positions["300394"].shares == 100
        assert pf.cash < 100_000

    def test_buy_insufficient_cash(self):
        pf = PortfolioV30(initial_cash=1_000)
        b = PaperBrokerV30(portfolio=pf)
        o = b.submit_order("300394", "示例", OrderSideV30.BUY, 1000, 100.0)
        assert o.status == "REJECTED"

    def test_sell(self):
        pf = PortfolioV30(initial_cash=100_000)
        b = PaperBrokerV30(portfolio=pf)
        b.submit_order("300394", "示例", OrderSideV30.BUY, 100, 100.0)
        o = b.submit_order("300394", "示例", OrderSideV30.SELL, 40, 110.0)
        assert o.status == "FILLED"
        assert pf.positions["300394"].shares == 60

    def test_sell_without_position(self):
        pf = PortfolioV30(initial_cash=100_000)
        b = PaperBrokerV30(portfolio=pf)
        o = b.submit_order("300394", "示例", OrderSideV30.SELL, 10, 100.0)
        assert o.status == "REJECTED"

    def test_avg_price_on_add(self):
        pf = PortfolioV30(initial_cash=100_000)
        b = PaperBrokerV30(portfolio=pf)
        b.submit_order("300394", "示例", OrderSideV30.BUY, 100, 100.0)
        b.submit_order("300394", "示例", OrderSideV30.BUY, 100, 120.0)
        p = pf.positions["300394"]
        assert p.shares == 200
        # 执行价含滑点：100*1.0005 + 120*1.0005
        assert p.avg_price == pytest.approx(110.055)


class TestExecutionEngineV30:
    def test_execute(self):
        pf = PortfolioV30(initial_cash=1_000_000)
        b = PaperBrokerV30(portfolio=pf)
        e = ExecutionEngineV30(broker=b)
        orders = e.execute_targets(
            targets=[{"code": "300394", "target_weight": 0.2}],
            prices={"300394": 100.0},
            names={"300394": "示例"},
        )
        assert len(orders) == 1
        assert orders[0].status == "FILLED"
        assert orders[0].quantity == 2000  # 200000/100/100*100


class TestTradeReviewV30:
    def test_win(self):
        t = TradeReviewV30()
        r = t.review({"pnl_pct": 0.15, "holding_days": 10})
        assert r["result"] == "WIN"
        assert r["lessons"] == []

    def test_loss(self):
        t = TradeReviewV30()
        r = t.review({"pnl_pct": -0.08, "holding_days": 70})
        assert r["result"] == "LOSS"
        assert "检查止损纪律" in r["lessons"]
        assert "检查策略持仓周期" in r["lessons"]

    def test_neutral(self):
        t = TradeReviewV30()
        r = t.review({"pnl_pct": 0.0, "holding_days": 5})
        assert r["result"] == "NEUTRAL"


class TestMainV30:
    def test_main(self, capsys):
        import main_v30
        main_v30.main()
        out = capsys.readouterr().out
        assert "AI HEDGE FUND OS V3.0" in out
        assert "风险检查:" in out
        assert "V3.0 COMPLETE" in out
