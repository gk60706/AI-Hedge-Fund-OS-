"""盘中 AI 决策 Agent (V0.8)

汇总各信号评分，输出 BUY / SELL / HOLD 与置信度（模拟）。
"""


def intraday_decision(signals: list) -> dict:
    """盘中 AI 决策。

    :param signals: 信号列表，元素含 ``score``（缺省 50）
    :return: ``{"action": "BUY"|"SELL"|"HOLD", "confidence": float}``
    """
    score = 0
    for s in signals:
        score += s.get("score", 50)
    score /= len(signals)
    if score >= 80:
        action = "BUY"
    elif score <= 40:
        action = "SELL"
    else:
        action = "HOLD"
    return {"action": action, "confidence": score / 100}
