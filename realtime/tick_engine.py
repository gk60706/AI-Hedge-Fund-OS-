"""Tick 数据引擎 (V0.8)

内存缓存每只股票的最新 tick。
"""


class TickEngine:
    """Tick 数据缓存引擎。"""

    def __init__(self):
        self.ticks = {}

    def update(self, tick: dict) -> None:
        """更新某只股票的最新 tick。"""
        code = tick["code"]
        self.ticks[code] = tick

    def get(self, code: str):
        """取某只股票的最新 tick。"""
        return self.ticks.get(code)
