"""风险预算模型 (V0.6)

等权风险预算：将总资金按股票数量等分，输出每只股票的权重与分配资金。
"""


def risk_budget(stocks: list, total_money: float) -> list:
    """按等权风险预算分配资金。

    :param stocks: 股票列表，元素含 ``code``
    :param total_money: 总资金
    :return: ``[{"code", "weight", "capital"}]``
    """
    result = []
    weight = 1 / len(stocks)
    for s in stocks:
        result.append({
            "code": s["code"],
            "weight": weight,
            "capital": total_money * weight,
        })
    return result
