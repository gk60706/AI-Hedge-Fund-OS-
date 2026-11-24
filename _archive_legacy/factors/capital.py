"""主力资金因子 (V0.5)

按主动买入/卖出量比评估主力资金意愿。
"""


def capital_factor(buy_volume: float, sell_volume: float) -> float:
    """主力资金因子评分。

    :param buy_volume: 主动买入量
    :param sell_volume: 主动卖出量
    :return: 0-100 的资金面得分
    """
    if sell_volume == 0:
        return 100
    ratio = buy_volume / sell_volume
    if ratio > 3:
        return 100
    elif ratio > 2:
        return 80
    elif ratio > 1:
        return 60
    else:
        return 30
