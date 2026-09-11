"""V2.2 自动股票池管理：观察池 → 候选池 → 重点池 → 持仓池。"""


class StockPool:
    """AI 股票池。"""

    def __init__(self):
        self.pool = {
            "watch": [],
            "candidate": [],
            "focus": [],
            "holding": [],
        }

    def add(self, category: str, stock) -> None:
        """把股票加入指定池子。"""
        self.pool[category].append(stock)

    def get(self, category: str) -> list:
        """取指定池子全部股票。"""
        return self.pool[category]
