"""V1.8 交易成本模型：佣金 + 印花税。"""


class TransactionCost:
    """模拟 A 股交易成本（佣金万三、最低 5 元；印花税千一）。"""

    def calculate(self, amount: float) -> float:
        """按成交金额计算交易成本。

        Args:
            amount: 成交金额。

        Returns:
            佣金（max(金额×万三, 5)）+ 印花税（金额×千一）。
        """
        commission = max(amount * 0.0003, 5)
        stamp_tax = amount * 0.001
        return commission + stamp_tax
