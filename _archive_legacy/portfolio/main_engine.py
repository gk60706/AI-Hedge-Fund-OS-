"""多策略组合入口 (V0.6)

将多因子评分与 AI 基金经理串联，一键生成模拟组合。
"""
from strategies.multi_factor import calculate_factor
from agents.portfolio_agent import portfolio_manager


def run_portfolio(stocks: list) -> list:
    """运行多策略组合流程。

    :param stocks: 候选股票列表
    :return: 模拟投资组合
    """
    factors = []
    for s in stocks:
        factors.append(calculate_factor(s))
    portfolio = portfolio_manager(factors)
    return portfolio
