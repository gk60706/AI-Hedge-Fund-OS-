"""组合层 (V0.7)

目录树中声明的 trading/portfolio.py：聚合账户、持仓与盈亏，形成组合快照。
（ChatGPT 未给出该文件代码，按 V0.7 架构图补齐最小实现。）
"""
from trading.account import Account
from trading.performance import calculate_pnl


class Portfolio:
    """模拟投资组合：账户 + 持仓 + 盈亏聚合。"""

    def __init__(self, cash: float = 1000000):
        self.account = Account(cash=cash)

    def snapshot(self, market: dict) -> dict:
        """组合快照。

        :param market: 最新行情 ``{code: price}``
        """
        self.account.update_asset(market)
        pnl = calculate_pnl(self.account.positions, market)
        return {
            "balance": self.account.get_balance(),
            "pnl": pnl,
        }
