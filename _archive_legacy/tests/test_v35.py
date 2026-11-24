"""V3.5 AI Portfolio Backtest & Stress Test Engine 单元测试。"""

import numpy as np
import pandas as pd
import pytest


class TestPerformanceMetrics:
    def test_calculate_basic(self):
        from metrics.performance import PerformanceMetrics

        # 初始 100 万 + 252 期恒定 1% 收益
        equity = np.concatenate(
            [[1_000_000], 1_000_000 * np.cumprod(np.full(252, 1.01))]
        )
        metrics = PerformanceMetrics().calculate(equity)
        # 252 期 = 1 年，年化复合收益等于总收益 1.01**252-1
        assert metrics["total_return"] == pytest.approx(1.01**252 - 1, rel=1e-9)
        assert metrics["cagr"] == pytest.approx(1.01**252 - 1, rel=1e-9)
        assert metrics["annual_volatility"] == pytest.approx(0.0, abs=1e-9)
        assert np.isfinite(metrics["sharpe"])
        assert metrics["max_drawdown"] == pytest.approx(0.0)
        assert metrics["win_rate"] == pytest.approx(1.0)
        assert metrics["profit_factor"] == 0.0  # 无亏损
        assert metrics["final_equity"] == pytest.approx(equity[-1])

    def test_calculate_short_curve(self):
        from metrics.performance import PerformanceMetrics

        assert PerformanceMetrics().calculate([100.0]) == {}

    def test_calculate_drawdown(self):
        from metrics.performance import PerformanceMetrics

        # 100 -> 150 -> 120 -> 160
        equity = [100.0, 150.0, 120.0, 160.0]
        metrics = PerformanceMetrics().calculate(equity, periods_per_year=2)
        assert metrics["total_return"] == pytest.approx(0.6)
        assert metrics["max_drawdown"] == pytest.approx(120 / 150 - 1)
        assert metrics["final_equity"] == pytest.approx(160.0)

    def test_calculate_known_win_rate(self):
        from metrics.performance import PerformanceMetrics

        # 10 期，5 涨 3 跌 2 平（returns==0 不算赢）
        equity = np.array([100.0])
        for r in [0.01, -0.01, 0.02, -0.02, 0.0, 0.03, -0.01, 0.01, 0.0, 0.02]:
            equity = np.append(equity, equity[-1] * (1 + r))
        metrics = PerformanceMetrics().calculate(equity, periods_per_year=252)
        assert metrics["win_rate"] == pytest.approx(5 / 10)


class TestBenchmarkEngine:
    def test_calculate_equity(self):
        from backtest.benchmark import BenchmarkEngine

        prices = [100.0, 110.0, 99.0]
        equity = BenchmarkEngine().calculate_equity(prices, initial_capital=1_000_000)
        assert equity[0] == pytest.approx(1_000_000)
        assert equity[-1] == pytest.approx(1_000_000 * 1.10 * 0.90)

    def test_empty(self):
        from backtest.benchmark import BenchmarkEngine

        equity = BenchmarkEngine().calculate_equity([])
        assert len(equity) == 0


class TestPortfolioBacktest:
    def _data(self):
        dates = pd.bdate_range("2024-01-01", periods=5)
        prices = pd.DataFrame(
            {
                "A": [100.0, 102.0, 101.0, 104.0, 106.0],
                "B": [50.0, 51.0, 49.0, 52.0, 53.0],
            },
            index=dates,
        )
        weights = pd.DataFrame(
            {
                "A": [0.5, 0.5, 0.5, 0.5, 0.5],
                "B": [0.5, 0.5, 0.5, 0.5, 0.5],
            },
            index=dates,
        )
        return prices, weights

    def test_run_shape(self):
        from backtest.portfolio_backtest import PortfolioBacktest

        prices, weights = self._data()
        result = PortfolioBacktest(initial_capital=100_000).run(prices, weights)
        assert len(result["equity_curve"]) == len(prices)
        # 第 0 天即按目标权重买入（付佣金+滑点），首日净值略低于初始资金
        assert result["equity_curve"][0] <= 100_000
        assert result["equity_curve"][0] > 99_000
        assert result["turnover"] >= 0
        assert set(result["holdings"]) == {"A", "B"}

    def test_run_buy_sell(self):
        from backtest.portfolio_backtest import PortfolioBacktest

        # 第 1 天全仓 A，第 2 天全仓 B：触发卖出 A + 买入 B
        dates = pd.bdate_range("2024-01-01", periods=3)
        prices = pd.DataFrame({"A": [100.0, 100.0, 100.0], "B": [100.0, 100.0, 100.0]}, index=dates)
        weights = pd.DataFrame(
            {"A": [1.0, 0.0, 0.0], "B": [0.0, 1.0, 1.0]}, index=dates
        )
        bt = PortfolioBacktest(initial_capital=100_000, commission=0.0003, stamp_duty=0.0005, slippage=0.0005)
        result = bt.run(prices, weights)
        # 卖出 A 收印花税，现金不足以买满 B，期末净值略低于 100 万
        assert result["equity_curve"][-1] < 100_000
        assert result["holdings"]["B"] > 0
        assert result["turnover"] > 0

    def test_run_cash_limited(self):
        from backtest.portfolio_backtest import PortfolioBacktest

        dates = pd.bdate_range("2024-01-01", periods=2)
        prices = pd.DataFrame({"A": [100.0, 100.0]}, index=dates)
        weights = pd.DataFrame({"A": [0.0, 0.0]}, index=dates)  # 不买
        result = PortfolioBacktest(initial_capital=100_000).run(prices, weights)
        assert result["equity_curve"][-1] == pytest.approx(100_000)
        assert result["holdings"]["A"] == pytest.approx(0.0)


class TestTimeSeriesSplit:
    def test_split_ratios(self):
        from validation.train_test import TimeSeriesSplit

        df = pd.DataFrame({"x": range(100)})
        split = TimeSeriesSplit().split(df)
        assert len(split["train"]) == 60
        assert len(split["validation"]) == 20
        assert len(split["test"]) == 20
        # 不重排、顺序保持
        assert split["test"].iloc[0]["x"] == 80


class TestWalkForwardEngine:
    def test_generate_windows(self):
        from backtest.walk_forward import WalkForwardEngine

        df = pd.DataFrame({"x": range(30)})
        windows = WalkForwardEngine(train_size=10, test_size=5).generate_windows(df)
        # 0-15, 5-20, 10-25, 15-30 -> 4 个窗口
        assert len(windows) == 4
        assert len(windows[0]["train"]) == 10
        assert len(windows[0]["test"]) == 5
        assert windows[0]["test"].iloc[0]["x"] == 10
        assert windows[-1]["test"].iloc[-1]["x"] == 29

    def test_insufficient_data(self):
        from backtest.walk_forward import WalkForwardEngine

        df = pd.DataFrame({"x": range(5)})
        assert WalkForwardEngine(train_size=10, test_size=5).generate_windows(df) == []


class TestOOSValidator:
    def test_pass(self):
        from validation.oos import OOSValidator

        result = OOSValidator().evaluate({"sharpe": 1.2, "max_drawdown": -0.15})
        assert result == {"passed": True, "reason": "PASS"}

    def test_sharpe_too_low(self):
        from validation.oos import OOSValidator

        result = OOSValidator().evaluate({"sharpe": 0.3, "max_drawdown": -0.05})
        assert result["passed"] is False
        assert result["reason"] == "SHARPE_TOO_LOW"

    def test_drawdown_too_high(self):
        from validation.oos import OOSValidator

        result = OOSValidator().evaluate({"sharpe": 1.2, "max_drawdown": -0.40})
        assert result["passed"] is False
        assert result["reason"] == "DRAWDOWN_TOO_HIGH"

    def test_empty_metrics(self):
        from validation.oos import OOSValidator

        result = OOSValidator().evaluate({})
        assert result["passed"] is False
        assert result["reason"] == "NO_METRICS"


class TestStressTestEngine:
    def test_crash(self):
        from backtest.stress_test import StressTestEngine

        prices = np.full(100, 100.0)
        crashed = StressTestEngine().apply_crash(prices, -0.20)
        assert crashed[0] == pytest.approx(100.0)
        assert crashed[50] == pytest.approx(80.0)
        assert crashed[-1] == pytest.approx(80.0)

    def test_high_volatility_shape(self):
        from backtest.stress_test import StressTestEngine

        prices = np.full(50, 100.0)
        out = StressTestEngine().apply_high_volatility(prices, seed=42)
        assert len(out) == 50
        assert np.all(np.isfinite(out))

    def test_run_keys(self):
        from backtest.stress_test import StressTestEngine

        prices = np.full(20, 100.0)
        results = StressTestEngine().run(prices)
        assert set(results) == {"crash_20", "crash_30", "high_volatility"}
        assert results["crash_20"][-1] == pytest.approx(80.0)
        assert results["crash_30"][-1] == pytest.approx(70.0)


class TestPortfolioComparison:
    def test_compare(self):
        from metrics.comparison import PortfolioComparison

        pm = {"total_return": 0.3, "cagr": 0.1, "sharpe": 1.5, "max_drawdown": -0.2}
        bm = {"total_return": 0.2, "cagr": 0.08, "sharpe": 1.0, "max_drawdown": -0.3}
        result = PortfolioComparison().compare(pm, bm)
        assert result["return_difference"] == pytest.approx(0.1)
        assert result["cagr_difference"] == pytest.approx(0.02)
        assert result["sharpe_difference"] == pytest.approx(0.5)
        assert result["drawdown_difference"] == pytest.approx(0.1)


class TestRobustness:
    def test_score_bounds(self):
        from metrics.robustness import robustness_score

        good = {"sharpe": 2.0, "sortino": 2.5, "calmar": 2.0, "profit_factor": 2.0, "max_drawdown": 0.0}
        assert robustness_score(good) == pytest.approx(100.0)
        bad = {"sharpe": 0.0, "sortino": 0.0, "calmar": 0.0, "profit_factor": 0.0, "max_drawdown": -1.0}
        assert robustness_score(bad) == pytest.approx(0.0)

    def test_grade(self):
        from metrics.robustness import robustness_grade

        assert robustness_grade(90) == "EXCELLENT"
        assert robustness_grade(70) == "GOOD"
        assert robustness_grade(55) == "WATCH"
        assert robustness_grade(40) == "WEAK"
        assert robustness_grade(20) == "RETIRE"

    def test_integration_with_main_metrics(self):
        from metrics.performance import PerformanceMetrics
        from metrics.robustness import robustness_score, robustness_grade

        equity = 1_000_000 * np.cumprod(np.full(504, 1.001))
        metrics = PerformanceMetrics().calculate(equity)
        score = robustness_score(metrics)
        assert 0 <= score <= 100
        assert robustness_grade(score) in ("EXCELLENT", "GOOD", "WATCH", "WEAK", "RETIRE")
