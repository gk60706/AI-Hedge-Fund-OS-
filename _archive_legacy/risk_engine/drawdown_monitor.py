"""V2.5 最大回撤监控。"""


class DrawdownMonitor:
    """最大回撤计算与闸门（回撤>15% 停止）。"""

    def calculate(self, equity):
        """计算最大回撤（负数）。"""
        peak = equity[0]
        max_drawdown = 0
        for value in equity:
            if value > peak:
                peak = value
            drawdown = (value / peak - 1)
            max_drawdown = min(max_drawdown, drawdown)
        return max_drawdown

    def check(self, drawdown):
        if drawdown < -0.15:
            return "STOP"
        return "NORMAL"
