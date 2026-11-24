"""AI 交易决策总入口 (V0.9)

汇总市场/个股/新闻，交由 AI CIO 输出交易决策。
"""
from brain.cio_agent import cio_decision


def run_ai_trader(market, stock, news) -> dict:
    """运行 AI 交易决策。

    :param market: 市场环境
    :param stock: 股票信息
    :param news: 新闻信息
    :return: ``{"decision": ...}``
    """
    decision = cio_decision(market, stock, news)
    return {"decision": decision}
