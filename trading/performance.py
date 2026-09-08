"""盈亏统计 (V0.7)

按持仓成本与最新价格计算浮盈浮亏。
"""


def calculate_pnl(positions: dict, prices: dict) -> list:
    """计算盈亏。

    :param positions: 持仓 dict（``{code: {volume, cost}}``）
    :param prices: 最新价格 dict（``{code: price}``）
    :return: ``[{"code", "pnl", "return"}]``
    """
    result = []
    for code, pos in positions.items():
        market_value = pos["volume"] * prices[code]
        cost = pos["cost"]
        pnl = market_value - cost
        result.append({
            "code": code,
            "pnl": pnl,
            "return": pnl / cost if cost else 0,
        })
    return result
