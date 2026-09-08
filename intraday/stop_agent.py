"""自动止盈止损 Agent (V0.8)

达到 20% 止盈或 8% 止损触发 SELL（模拟信号）。
"""


def take_profit_stop(cost: float, price: float) -> dict:
    """自动止盈。

    :param cost: 成本价
    :param price: 当前价
    :return: ``{"action": "SELL"|"HOLD", "reason"?: ...}``
    """
    profit = (price - cost) / cost
    if profit >= 0.20:
        return {"action": "SELL", "reason": "达到20%止盈"}
    return {"action": "HOLD"}


def stop_loss(cost: float, price: float) -> dict:
    """自动止损。

    :param cost: 成本价
    :param price: 当前价
    :return: ``{"action": "SELL"|"HOLD", "reason"?: ...}``
    """
    loss = (price - cost) / cost
    if loss <= -0.08:
        return {"action": "SELL", "reason": "触发8%止损"}
    return {"action": "HOLD"}
