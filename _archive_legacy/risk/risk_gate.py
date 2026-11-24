"""V1.7 风险闸门：RL Agent 决策必须经过风控审批（模拟盘前置）。"""


class RiskGate:
    """风险闸门。"""

    def check(self, action, portfolio_value, max_drawdown, daily_loss) -> dict:
        if daily_loss <= -0.03:
            return {"approved": False, "reason": "DAILY_LOSS_LIMIT"}
        if max_drawdown >= 0.10:
            return {"approved": False, "reason": "MAX_DRAWDOWN"}
        return {"approved": True, "reason": "NORMAL"}
