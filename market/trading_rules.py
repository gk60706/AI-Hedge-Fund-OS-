"""V3.6 AShareTradingRules：A 股交易规则（T+1）。

如果今天买入，当天不能卖。V3.6 简化实现：当前日期买入的股份不可卖。
"""

from __future__ import annotations

from collections import defaultdict


class AShareTradingRules:
    def __init__(self):
        self.buy_lots = defaultdict(int)

    def record_buy(self, code: str, shares: int, date):
        self.buy_lots[(code, str(date))] += shares

    def sellable_shares(self, code: str, total_shares: int, date):
        # V3.6 简化实现：
        # 当前日期买入的股份不可卖
        today_bought = self.buy_lots.get((code, str(date)), 0)
        return max(total_shares - today_bought, 0)
