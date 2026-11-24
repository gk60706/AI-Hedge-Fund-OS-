"""V1.5 AI 盘中交易 Agent：综合多信号决定 BUY/SELL/HOLD。"""


class IntradayTrader:
    """盘中交易 Agent（模拟决策）。"""

    def decide(self, signals: list) -> str:
        if not signals:
            return "HOLD"
        score = 0
        for s in signals:
            score += s
        score /= len(signals)
        if score >= 80:
            return "BUY"
        elif score <= 40:
            return "SELL"
        return "HOLD"
