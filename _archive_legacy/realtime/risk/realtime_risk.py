"""V2.3 实时风险控制：最大仓位 / 单票风险 / 日亏损监控。"""


class RealTimeRisk:
    """实时风控中心。"""

    def check(self, portfolio: dict) -> dict:
        """检查组合风险。

        Args:
            portfolio: {"loss": float, "position": float}。

        Returns:
            {"status": "STOP_TRADING" | "REDUCE_POSITION" | "NORMAL"}
        """
        if portfolio["loss"] < -0.03:
            return {"status": "STOP_TRADING"}
        if portfolio["position"] > 0.5:
            return {"status": "REDUCE_POSITION"}
        return {"status": "NORMAL"}
