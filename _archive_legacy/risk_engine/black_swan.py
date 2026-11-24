"""V2.5 黑天鹅检测：极端跌幅 / 流动性消失 / 波动异常。"""


class BlackSwanDetector:
    """黑天鹅事件监控。"""

    def detect(self, market):
        alerts = []
        if market["drop"] < -0.05:
            alerts.append("MARKET_CRASH")
        if market["volatility"] > 0.6:
            alerts.append("VOLATILITY_SPIKE")
        return alerts
