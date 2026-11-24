"""V0.3 机会发现 Agent：主力资金评分 + 基础分，排序出候选池。"""
from __future__ import annotations


def opportunity_score(item: dict) -> float:
    score = 0
    # 主力资金（权重 0.6）
    score += item["fund_score"] * 0.6
    # 基础评分
    score += 30
    return score


def rank_opportunity(stocks: list[dict]) -> list[dict]:
    result = []
    for s in stocks:
        s["opportunity_score"] = opportunity_score(s)
        result.append(s)
    return sorted(result, key=lambda x: x["opportunity_score"], reverse=True)
