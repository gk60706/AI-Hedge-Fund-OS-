"""AI 交易 Agent (V0.7)

根据决策分数生成模拟交易信号（BUY/SELL/HOLD）。
"""


def trader_agent(decision: dict) -> dict:
    """AI 交易 Agent。

    :param decision: 含 ``code``/``score``/``price`` 的决策
    :return: 交易信号 ``{"code", "action", "price", "volume": 1000}``
    """
    score = decision["score"]
    if score >= 80:
        action = "BUY"
    elif score <= 40:
        action = "SELL"
    else:
        action = "HOLD"
    return {
        "code": decision["code"],
        "action": action,
        "price": decision["price"],
        "volume": 1000,
    }
