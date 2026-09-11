"""V2.4 交易日志系统。"""
import json


class TradeJournal:
    """交易日志：记录并落盘。"""

    def __init__(self):
        self.logs = []

    def record(self, trade):
        self.logs.append(trade)

    def save(self, path):
        with open(path, "w", encoding="utf8") as f:
            json.dump(self.logs, f, ensure_ascii=False, indent=2)
