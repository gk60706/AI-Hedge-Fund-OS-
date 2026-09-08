"""V0.3 主力资金 Agent。"""
from __future__ import annotations

from scanners.capital_flow import calculate_main_force_score
from scanners.order_book import get_order_book


def fund_agent(stock) -> dict:
    """对单只股票做主力资金评分；stock 为含 代码/名称/涨跌幅/量比 的 dict 或 Series。"""
    code = str(stock["代码"]).zfill(6)
    book = get_order_book(code)
    score = calculate_main_force_score(
        book,
        stock.get("量比", 1) if hasattr(stock, "get") else 1,
        stock["涨跌幅"],
    )
    return {
        "code": code,
        "name": stock["名称"],
        "fund_score": score,
        "order_book": book,
    }
