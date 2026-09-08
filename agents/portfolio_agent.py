"""AI 基金经理 Agent (V0.6)

按 Alpha 排序取前 10 只股票，等权分配资金，构建模拟组合。
"""


def portfolio_manager(stocks: list, money: float = 1000000) -> list:
    """AI 基金经理：构建模拟投资组合。

    :param stocks: 含 ``code``/``alpha`` 的候选股票列表
    :param money: 总资金（默认 100 万）
    :return: ``[{"code", "alpha", "capital", "position"}]``（最多 10 只）
    """
    ranked = sorted(stocks, key=lambda x: x["alpha"], reverse=True)
    selected = ranked[:10]
    weight = money / 10
    portfolio = []
    for s in selected:
        portfolio.append({
            "code": s["code"],
            "alpha": s["alpha"],
            "capital": weight,
            "position": 0.1,
        })
    return portfolio
