"""V2.2 自动投资研究流水线（Autonomous Research Pipeline）单元测试。"""

import pytest

from automation.scheduler import AIScheduler
from automation.daily_pipeline import DailyPipeline
from scanner.stock_scanner import StockScanner, StockScannerV22
from scanner.opportunity_rank import OpportunityRank
from committee.voting import VotingSystem, InvestmentCommittee
from database.stock_pool import StockPool
from reports.morning_report import MorningReport, morning_report
from reports.evening_report import EveningReport, evening_report


class TestAIScheduler:
    def test_add_daily_task(self):
        s = AIScheduler()
        s.add_daily_task(lambda: None, hour=8, minute=0)
        assert len(s.scheduler.get_jobs()) == 1

    def test_add_two_tasks(self):
        s = AIScheduler()
        s.add_daily_task(lambda: None, hour=8, minute=0)
        s.add_daily_task(lambda: None, hour=15, minute=30)
        assert len(s.scheduler.get_jobs()) == 2


class TestStockScannerV22:
    def test_scan_scores(self):
        market = [
            {"code": "300394", "momentum": 1, "volume_ratio": 2, "fund_flow": 1},
            {"code": "688568", "momentum": 1, "volume_ratio": 1.8, "fund_flow": 1},
            {"code": "000001", "momentum": 0, "volume_ratio": 1.0, "fund_flow": 0},
        ]
        out = StockScannerV22(market).scan()
        # 300394/688568: 30+30+40=100；000001: 0 < 70 不入围
        assert len(out) == 2
        assert out[0]["score"] == 100
        assert [x["code"] for x in out] == ["300394", "688568"]

    def test_old_v14_interface_kept(self):
        # V1.4 老接口：StockScanner(agents).scan(stocks)
        class FakeAgent:
            def analyze(self, stock):
                return {"score": 50}

        out = StockScanner([FakeAgent()]).scan([{"code": "600519"}])
        assert out[0]["score"] == 50


class TestOpportunityRank:
    def test_rank_top50(self):
        stocks = [{"code": f"c{i}", "score": i} for i in range(60)]
        out = OpportunityRank().rank(stocks)
        assert len(out) == 50
        assert out[0]["code"] == "c59"


class TestInvestmentCommittee:
    def test_buy_majority(self):
        assert InvestmentCommittee().vote(["BUY", "BUY", "BUY", "HOLD", "SELL"]) == "BUY"

    def test_sell_majority(self):
        assert InvestmentCommittee().vote(["SELL", "SELL", "SELL", "BUY", "BUY"]) == "SELL"

    def test_hold_otherwise(self):
        assert InvestmentCommittee().vote(["BUY", "HOLD", "HOLD", "SELL", "HOLD"]) == "HOLD"

    def test_old_v13_interface_kept(self):
        # V1.3 老接口：VotingSystem.vote 返回 dict（含 decision）
        out = VotingSystem().vote([{"score": 90}, {"score": 90}, {"score": 50}])
        assert out["decision"] == "BUY"


class TestStockPool:
    def test_add_get(self):
        pool = StockPool()
        pool.add("watch", "300394")
        pool.add("candidate", "688568")
        pool.add("focus", "600519")
        pool.add("holding", "000858")
        assert pool.get("watch") == ["300394"]
        assert pool.get("holding") == ["000858"]


class TestMorningReport:
    def test_generate(self):
        out = MorningReport().generate("震荡", "300394, 688568")
        assert "# AI基金每日晨报" in out
        assert "等待市场确认" in out

    def test_old_v10_interface_kept(self):
        out = morning_report("震荡", "300394")
        assert "# AI基金晨报" in out


class TestEveningReport:
    def test_generate(self):
        out = EveningReport().generate("买入300394", "+2.3%")
        assert "# AI基金每日复盘" in out
        assert "优化下一交易日策略" in out

    def test_old_v10_interface_kept(self):
        out = evening_report(["买入300394"])
        assert "# AI交易复盘" in out


class TestDailyPipeline:
    def test_run(self, capsys):
        market = [
            {"code": "300394", "momentum": 1, "volume_ratio": 2, "fund_flow": 1},
            {"code": "688568", "momentum": 1, "volume_ratio": 1.8, "fund_flow": 1},
        ]
        pipeline = DailyPipeline(StockScannerV22(market), InvestmentCommittee())
        result = pipeline.run()
        captured = capsys.readouterr()
        assert "开始AI基金每日研究" in captured.out
        assert "发现机会: 2" in captured.out
        assert result["decision"] == "BUY"
        assert len(result["stocks"]) == 2
