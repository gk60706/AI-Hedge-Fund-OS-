"""实时资金流 Agent (V0.8)

根据 tick 买卖方向统计资金流，输出 0-100 资金流评分。
"""


def capital_flow_score(ticks: list) -> float:
    """实时资金流评分。

    :param ticks: tick 列表，元素含 ``direction``（BUY/SELL）与 ``amount``
    :return: 0-100 资金流得分
    """
    buy = 0
    sell = 0
    for t in ticks:
        if t["direction"] == "BUY":
            buy += t["amount"]
        else:
            sell += t["amount"]
    if sell == 0:
        return 100
    ratio = buy / sell
    if ratio > 3:
        return 95
    elif ratio > 2:
        return 80
    elif ratio > 1:
        return 60
    return 30
