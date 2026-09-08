"""V0.4 基本面流水线：V0.3 机会池 → 基本面研究 → 按基本面评分排序。"""
from __future__ import annotations

from fundamental.fundamental_engine import run_fundamental_analysis
from scanners.scanner import scan_market


def run_ai_selection(top_n: int = 50) -> list[dict]:
    stocks = scan_market(top_n=top_n)
    result = []
    for stock in stocks:
        analysis = run_fundamental_analysis(
            financial={},
            news="",
            industry="AI 半导体",
            company=stock["name"],
        )
        stock.update(analysis)
        result.append(stock)
    return sorted(
        result,
        key=lambda x: x["fundamental_score"],
        reverse=True,
    )
