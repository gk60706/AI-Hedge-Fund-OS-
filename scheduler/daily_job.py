"""V3.0.3 每日自动运行调度器。

Windows 可用：python scheduler/daily_job.py
"""
from __future__ import annotations

from pipeline.investment_pipeline import (
    InvestmentPipeline,
)


def run_daily():
    print("Starting AI Hedge Fund daily job...")
    pipeline = InvestmentPipeline(
        portfolio_value=1_000_000
    )
    report = pipeline.run(scan_limit=50)
    path = pipeline.save_report(report)
    print(f"Report saved: {path}")


if __name__ == "__main__":
    run_daily()
