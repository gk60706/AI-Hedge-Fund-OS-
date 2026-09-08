"""价值因子 (V0.5)

PE 估值评分：低估值获得更高分数。
"""


def pe_factor(pe: float) -> float:
    """PE 估值评分。

    :param pe: 市盈率
    :return: 0-100 的估值得分（越低 PE 得分越高）
    """
    if pe < 20:
        return 90
    elif pe < 40:
        return 70
    elif pe < 80:
        return 50
    else:
        return 20
