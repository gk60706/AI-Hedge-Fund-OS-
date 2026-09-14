"""交易成本模型 (V3.3)

佣金 + 印花税 + 滑点；A 股卖出一方征收印花税。
"""
from __future__ import annotations


class TransactionCostModel:
    """A 股交易成本估计。

    注意：这里是模型参数，不代表券商实际费率；
    后续接入券商时应该从账户配置读取。
    """

    def __init__(
        self,
        commission: float = 0.0003,
        stamp_duty: float = 0.0005,
        slippage: float = 0.0005,
    ):
        self.commission = commission
        self.stamp_duty = stamp_duty
        self.slippage = slippage

    def estimate(
        self,
        trade_value: float,
        side: str,
    ) -> float:
        """估计单笔交易总成本。

        :param trade_value: 交易金额（元）。
        :param side: 方向，"BUY" 或 "SELL"。
        :return: 成本金额（元）。
        """
        trade_value = abs(float(trade_value))
        commission_cost = trade_value * self.commission
        slippage_cost = trade_value * self.slippage
        stamp_cost = 0.0
        if side.upper() == "SELL":
            stamp_cost = trade_value * self.stamp_duty
        return commission_cost + slippage_cost + stamp_cost
