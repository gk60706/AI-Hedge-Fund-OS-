"""V1.6 多模型融合预测：加权得分 → BUY/SELL/HOLD 信号。"""


class EnsemblePredictor:
    """多模型融合预测器。"""

    def predict(self, xgb: float, lstm: float, transformer: float) -> dict:
        score = xgb * 0.5 + lstm * 0.3 + transformer * 0.2
        if score > 0.75:
            signal = "BUY"
        elif score < 0.35:
            signal = "SELL"
        else:
            signal = "HOLD"
        return {
            "score": score,
            "signal": signal,
        }
