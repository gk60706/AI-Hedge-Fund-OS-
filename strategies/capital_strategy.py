"""主力资金策略 (V0.6)

按主动买卖量比给股票打分（0-100）。
"""


def capital_score(stock: dict) -> float:
    """主力资金策略评分。

    :param stock: 含 ``buy_volume``/``sell_volume`` 的股票 dict
    :return: 0-100 的资金面得分
    """
    buy = stock.get("buy_volume", 0)
    sell = stock.get("sell_volume", 1)
    ratio = buy / sell
    if ratio > 3:
        return 95
    elif ratio > 2:
        return 80
    elif ratio > 1:
        return 60
    else:
        return 30
