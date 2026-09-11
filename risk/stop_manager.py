"""V2.4 止盈止损系统。"""


class StopManager:
    """止盈止损：亏损 8% 止损，盈利 20% 止盈。"""

    def check(self, buy_price, current_price):
        change = (current_price / buy_price - 1)
        if change <= -0.08:
            return "STOP_LOSS"
        if change >= 0.20:
            return "TAKE_PROFIT"
        return "HOLD"
