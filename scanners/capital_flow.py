"""V0.3 主力资金评分模型。"""
from __future__ import annotations


def calculate_main_force_score(order_book: dict, volume_ratio: float, change: float) -> int:
    """基于五档买卖力量 + 量比 + 涨幅计算主力吸筹评分（0-100）。"""
    score = 50
    # 五档买卖力量
    buy = order_book["buy5_volume"]
    sell = order_book["sell5_volume"]
    if sell == 0:
        ratio = 10
    else:
        ratio = buy / sell
    if ratio > 2:
        score += 25
    elif ratio > 1.3:
        score += 15
    elif ratio < 0.7:
        score -= 20
    # 成交量
    if volume_ratio > 2:
        score += 15
    # 涨幅
    if 2 < change < 8:
        score += 10
    if change > 9:
        score -= 10
    return max(0, min(100, score))
