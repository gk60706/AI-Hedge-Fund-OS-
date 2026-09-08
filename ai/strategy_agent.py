"""AI 策略评价 Agent (V0.5)

根据回测结果（收益/回撤/夏普）给策略打分，并给出 KEEP / DROP 决策。
"""


def evaluate_strategy(result: dict) -> dict:
    """评价一次回测结果。

    :param result: 含 ``return``，可选 ``drawdown``/``sharpe`` 的回测摘要
    :return: ``{"score": int, "status": "KEEP"|"DROP"}``
    """
    score = 0
    if result["return"] > 0.2:
        score += 40
    elif result["return"] > 0.1:
        score += 20
    if result.get("drawdown", 1) < 0.15:
        score += 30
    if result.get("sharpe", 0) > 1:
        score += 30
    if score >= 80:
        status = "KEEP"
    else:
        status = "DROP"
    return {"score": score, "status": status}
