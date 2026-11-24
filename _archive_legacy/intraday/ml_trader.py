"""V1.6 AI 交易信号 Agent：融合预测 → 开仓/平仓/等待（模拟）。"""


class MLTrader:
    """ML 交易信号 Agent（模拟决策，无实盘接口）。"""

    def decide(self, prediction: dict) -> dict:
        if prediction["signal"] == "BUY":
            return {
                "action": "OPEN_POSITION",
                "confidence": prediction["score"],
            }
        if prediction["signal"] == "SELL":
            return {
                "action": "CLOSE_POSITION",
            }
        return {
            "action": "WAIT",
        }
