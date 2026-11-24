"""动态调仓系统 (V0.6)

对比旧/新组合，生成模拟调仓订单（BUY/SELL）。
"""


def rebalance(old: list, new: list) -> list:
    """生成调仓订单。

    :param old: 旧持仓列表，元素含 ``code``
    :param new: 新目标组合列表，元素含 ``code``
    :return: ``[{"action": "BUY"|"SELL", "code": ...}]``
    """
    orders = []
    old_dict = {x["code"]: x for x in old}
    new_dict = {x["code"]: x for x in new}
    for code in new_dict:
        if code not in old_dict:
            orders.append({"action": "BUY", "code": code})
    for code in old_dict:
        if code not in new_dict:
            orders.append({"action": "SELL", "code": code})
    return orders
