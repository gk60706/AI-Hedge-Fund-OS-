"""市场环境 Agent (V0.9)

根据指数涨幅、北向资金、量比输出市场评分（BULL/NORMAL）。
"""


def analyze_market(data: dict) -> dict:
    """分析市场环境。

    :param data: 含 ``index_change``/``north_money``/``volume_ratio`` 的行情数据
    :return: ``{"market_score": float, "status": "BULL"|"NORMAL"}``
    """
    score = 50
    if data["index_change"] > 1:
        score += 20
    if data["north_money"] > 0:
        score += 15
    if data["volume_ratio"] > 1.5:
        score += 10
    return {
        "market_score": score,
        "status": "BULL" if score > 70 else "NORMAL",
    }
