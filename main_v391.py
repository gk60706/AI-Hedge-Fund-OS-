"""AI Hedge Fund OS V3.9.1 - unified Research Pipeline entry point (dump verbatim)."""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from core.config import get_settings
from core.logging import configure_logging
from data.akshare_client import AkShareClientV391
from data.price_loader import normalize_daily
from research.pipeline import ResearchPipeline
from research.report import write_report


def make_demo_panel(n_stocks=80, n_days=900, seed=42):
    """Synthetic panel. 只用于测试 V3.9.1 软件架构。不代表真实市场收益。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    codes = [f"{300000 + i:06d}" for i in range(n_stocks)]
    rows = []
    for code in codes:
        price = 10 + rng.random() * 20
        stock_bias = rng.normal()
        for date in dates:
            daily_return = rng.normal(0, 0.018)
            price = max(1, price * (1 + daily_return))
            pe = max(1, 20 + rng.normal(0, 5))
            pb = max(0.3, 2 + rng.normal(0, 0.6))
            value = 1 / pe
            momentum = rng.normal() + 0.15 * stock_bias
            quality = rng.normal() + 0.10 * stock_bias
            volatility = abs(rng.normal(0.25, 0.08))
            liquidity = abs(rng.normal(2e8, 5e7))
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "open": price * (1 + rng.normal(0, 0.004)),
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": abs(rng.normal(2e6, 5e5)),
                    "amount": liquidity,
                    "turnover": abs(rng.normal(2, 0.5)),
                    "pe": pe,
                    "pb": pb,
                    "value": value,
                    "momentum": momentum,
                    "quality": quality,
                    "volatility": volatility,
                    "liquidity": liquidity,
                }
            )
    return pd.DataFrame(rows)


def run_demo():
    settings = get_settings()
    panel = make_demo_panel(
        n_stocks=80,
        n_days=900,
        seed=settings.random_seed,
    )
    pipeline = ResearchPipeline(seed=settings.random_seed)
    result = pipeline.run(
        panel=panel,
        train_end="2024-01-31",
        oos_start="2024-02-01",
        n_candidates=300,
        horizon=1,
    )
    report_path = write_report(
        result,
        settings.report_dir / "V3.9.1_demo_report.md",
    )
    print()
    print("=" * 60)
    print("AI Hedge Fund OS V3.9.1")
    print("DEMO RESEARCH ENGINE")
    print("=" * 60)
    print()
    print("Champion Alpha:")
    print(result.champion)
    print()
    print("Data Audit:")
    print(result.audit)
    print()
    print("Backtest Metrics:")
    print(result.backtest_metrics)
    print()
    print("Report:")
    print(report_path)
    print()
    print("WARNING:")
    print("以上使用 synthetic data，不能用于判断真实股票收益能力。")


def run_stock(code, start, end):
    settings = get_settings()
    client = AkShareClientV391(settings.cache_dir)
    raw = client.get_daily(code, start, end)
    panel = normalize_daily(raw, code)
    print()
    print(f"{code} 数据获取成功")
    print()
    print(panel.tail(20).to_string(index=False))
    print()
    print("注意：单股票数据可以验证数据层，但不能完成真正的横截面 Alpha Discovery。")
    print("真正的 Alpha Research 必须建立多股票 Panel。")


def main():
    configure_logging(get_settings().log_level)
    parser = argparse.ArgumentParser(description="AI Hedge Fund OS V3.9.1")
    parser.add_argument("--mode", choices=["demo", "stock"], default="demo")
    parser.add_argument("--code", default="300394")
    parser.add_argument("--start", default="20200101")
    parser.add_argument("--end", default="20261231")
    args = parser.parse_args()
    if args.mode == "demo":
        run_demo()
    else:
        run_stock(args.code, args.start, args.end)


if __name__ == "__main__":
    main()
