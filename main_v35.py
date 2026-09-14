"""V3.5 AI Portfolio Backtest & Stress Test Engine 主程序。

先用模拟数据验证整个 Pipeline（先验证系统结构，再接真实数据）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.portfolio_backtest import PortfolioBacktest
from backtest.benchmark import BenchmarkEngine
from metrics.performance import PerformanceMetrics
from metrics.comparison import PortfolioComparison
from validation.train_test import TimeSeriesSplit
from validation.oos import OOSValidator
from backtest.stress_test import StressTestEngine


def create_demo_data(periods=1500, stocks=6):
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2021-01-01", periods=periods)
    returns = rng.normal(0.0003, 0.015, (periods, stocks))
    prices = 100 * np.cumprod(1 + returns, axis=0)
    codes = ["300394", "688568", "300274", "002594", "600519", "601318"]
    prices = pd.DataFrame(prices, index=dates, columns=codes)
    return prices


def create_target_weights(prices):
    codes = list(prices.columns)
    weights = pd.DataFrame(0.0, index=prices.index, columns=codes)
    # 示例组合
    base_weights = {
        "300394": 0.15,
        "688568": 0.15,
        "300274": 0.15,
        "002594": 0.15,
        "600519": 0.10,
        "601318": 0.10,
    }
    for code, weight in base_weights.items():
        weights[code] = weight
    return weights


def main():
    print("\n==============================")
    print("AI Hedge Fund OS V3.5")
    print("Portfolio Backtest & Stress Test")
    print("==============================\n")

    # ----------------------------
    # 数据
    # ----------------------------
    prices = create_demo_data()
    target_weights = create_target_weights(prices)

    # ----------------------------
    # 时间切分
    # ----------------------------
    splitter = TimeSeriesSplit()
    split = splitter.split(prices)
    print("Train:", len(split["train"]))
    print("Validation:", len(split["validation"]))
    print("OOS:", len(split["test"]))

    # ----------------------------
    # Portfolio Backtest
    # ----------------------------
    backtester = PortfolioBacktest()
    result = backtester.run(prices, target_weights)
    equity = result["equity_curve"]

    # ----------------------------
    # Metrics
    # ----------------------------
    metrics_engine = PerformanceMetrics()
    portfolio_metrics = metrics_engine.calculate(equity)
    print("\n===== PORTFOLIO =====")
    for key, value in portfolio_metrics.items():
        if isinstance(value, float):
            print(key, ":", round(value, 4))
        else:
            print(key, ":", value)

    # ----------------------------
    # Benchmark
    # ----------------------------
    benchmark_engine = BenchmarkEngine()
    benchmark_prices = prices.mean(axis=1)
    benchmark_equity = benchmark_engine.calculate_equity(benchmark_prices.values)
    benchmark_metrics = metrics_engine.calculate(benchmark_equity)
    print("\n===== BENCHMARK =====")
    for key, value in benchmark_metrics.items():
        if isinstance(value, float):
            print(key, ":", round(value, 4))

    # ----------------------------
    # Comparison
    # ----------------------------
    comparison = PortfolioComparison().compare(portfolio_metrics, benchmark_metrics)
    print("\n===== COMPARISON =====")
    for key, value in comparison.items():
        print(key, ":", round(value, 4))

    # ----------------------------
    # OOS
    # ----------------------------
    oos = OOSValidator().evaluate(portfolio_metrics)
    print("\n===== OOS =====")
    print(oos)

    # ----------------------------
    # Stress Test
    # ----------------------------
    stress = StressTestEngine()
    stress_results = stress.run(benchmark_prices.values)
    print("\n===== STRESS TEST =====")
    for name, values in stress_results.items():
        print(name, "periods=", len(values), "final=", round(float(values[-1]), 2))


if __name__ == "__main__":
    main()
