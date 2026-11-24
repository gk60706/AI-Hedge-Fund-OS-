"""V1.5 实时风险中心：持仓亏损超阈值触发卖出告警。"""


class RealTimeRisk:
    """实时风控中心（模拟告警，无实盘执行）。"""

    def check(self, position: list) -> list:
        alerts = []
        for stock in position:
            loss = stock["loss"]
            if loss < -0.08:
                alerts.append(
                    {
                        "code": stock["code"],
                        "action": "SELL",
                    }
                )
        return alerts
