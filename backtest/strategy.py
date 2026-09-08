"""回测策略 (V0.5)

基于 Backtrader 的简单 Alpha 策略：开仓买入，回撤 5% 止损卖出。
"""
import backtrader as bt


class AlphaStrategy(bt.Strategy):
    """Alpha 买入持有 + 回撤止损策略。"""

    params = dict(buy_threshold=70)

    def next(self):
        price = self.data.close[0]
        if not self.position:
            self.buy()
        else:
            if price < self.position.price * 0.95:
                self.sell()
