"""V0.3 全市场扫描器：股票池 → 主力资金评分 → 机会排序 → TOP50。"""
from __future__ import annotations

from agents.fund_agent import fund_agent
from agents.opportunity_agent import rank_opportunity
from scanners.stock_pool import create_stock_pool


def scan_market(top_n: int = 50) -> list[dict]:
    pool = create_stock_pool()
    if pool.empty:
        return []
    results: list[dict] = []
    total = len(pool)
    print(f"扫描股票数量: {total}")
    for _index, row in pool.iterrows():
        try:
            item = fund_agent(row)
            results.append(item)
        except Exception:
            continue
    ranking = rank_opportunity(results)
    return ranking[:top_n]
