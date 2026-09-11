"""V2.3 盘中异动检测：突然拉升 / 放量 / 快速下跌。"""


class AnomalyDetector:
    """实时异动检测器。"""

    def detect(self, tick: dict) -> list:
        """检测异动信号。

        Args:
            tick: {"change": float, "volume_ratio": float}。

        Returns:
            告警列表，如 ["FAST_RISE", "VOLUME_SPIKE"]。
        """
        alerts = []
        if tick["change"] > 5:
            alerts.append("FAST_RISE")
        if tick["volume_ratio"] > 5:
            alerts.append("VOLUME_SPIKE")
        return alerts
