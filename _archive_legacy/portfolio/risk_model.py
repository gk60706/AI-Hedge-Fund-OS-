"""风险模型 (V0.6)

组合风险估算：以持仓波动率均值作为组合风险，输出 HIGH/NORMAL 级别。
"""


def calculate_risk(portfolio: list) -> dict:
    """计算组合风险。

    :param portfolio: 持仓列表，元素含 ``volatility``（波动率，缺省 0.2）
    :return: ``{"portfolio_risk": float, "level": "HIGH"|"NORMAL"}``
    """
    risk = 0
    for stock in portfolio:
        volatility = stock.get("volatility", 0.2)
        risk += volatility
    risk /= len(portfolio)
    return {
        "portfolio_risk": risk,
        "level": "HIGH" if risk > 0.3 else "NORMAL",
    }
