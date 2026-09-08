"""T+0 策略 Agent (V0.8)

盘中相对开盘价低吸高抛（模拟信号）。
"""


def t0_strategy(morning_price: float, current_price: float) -> dict:
    """T+0 模拟策略。

    :param morning_price: 开盘/早盘价
    :param current_price: 当前价
    :return: ``{"action": "BUY"|"SELL"|"HOLD", "reason"?: ...}``
    """
    change = current_price / morning_price - 1
    if change < -0.03:
        return {"action": "BUY", "reason": "盘中低吸"}
    if change > 0.05:
        return {"action": "SELL", "reason": "盘中止盈"}
    return {"action": "HOLD"}
