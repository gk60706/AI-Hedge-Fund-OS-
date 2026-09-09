"""V1.5 T+0 交易策略：资金流低吸与盘中止盈（模拟决策）。"""


class T0Strategy:
    """T+0 策略（研究/模拟，无实盘接口）。"""

    def decide(self, price_change: float, capital_score: float) -> dict:
        if price_change < -0.03 and capital_score > 80:
            return {
                "action": "BUY",
                "reason": "资金流低吸",
            }
        if price_change > 0.05:
            return {
                "action": "SELL",
                "reason": "盘中止盈",
            }
        return {
            "action": "HOLD",
        }
