"""价值策略 (V0.6)

按 PE 估值给股票打分（0-100）。
"""


def value_score(stock: dict) -> float:
    """价值策略评分。

    :param stock: 含 ``pe``（市盈率）的股票 dict
    :return: 0-100 的估值得分
    """
    pe = stock.get("pe", 50)
    if pe < 15:
        return 90
    elif pe < 30:
        return 70
    elif pe < 60:
        return 50
    else:
        return 20
