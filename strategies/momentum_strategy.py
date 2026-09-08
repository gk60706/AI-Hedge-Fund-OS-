"""动量策略 (V0.6)

按 30 日收益率给股票打分（0-100）。
"""


def momentum_score(stock: dict) -> float:
    """动量策略评分。

    :param stock: 含 ``return_30``（30 日收益率）的股票 dict
    :return: 0-100 的动量得分
    """
    score = 50
    change30 = stock.get("return_30", 0)
    if change30 > 0.2:
        score += 30
    elif change30 > 0:
        score += 15
    else:
        score -= 20
    return min(max(score, 0), 100)
