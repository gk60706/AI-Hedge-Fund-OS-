"""实时交易循环 (V0.8)

汇集盘中信号，攒满 3 条后触发 AI 盘中决策（模拟，不接实盘）。
"""
from intraday.decision_agent import intraday_decision


class TradingMonitor:
    """实时交易监控循环。"""

    def __init__(self):
        self.signals = []

    def receive(self, signal: dict) -> None:
        """接收一条盘中信号。"""
        self.signals.append(signal)
        if len(self.signals) >= 3:
            decision = intraday_decision(self.signals)
            print("AI交易:", decision)
            self.signals = []
