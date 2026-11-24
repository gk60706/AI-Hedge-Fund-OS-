"""V2.7 Alpha 生成器：多模型融合（XGBoost + LSTM + 资金流）。"""


class AlphaGenerator:
    """Alpha 信号输出。"""

    def generate(self, xgb, lstm, capital):
        score = (
            xgb * 0.4
            + lstm * 0.3
            + capital * 0.3
        )
        return round(score, 3)
