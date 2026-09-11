"""V1.5 Tick 实时数据流：内存缓存最新 Tick。

V2.3 追加：push/latest（Tick 序列缓存），旧 update/get 保留。
"""
from datetime import datetime


class TickStream:
    """Tick 数据流缓存。"""

    def __init__(self) -> None:
        self.cache = {}
        self.ticks = []

    def update(self, tick: dict) -> None:
        self.cache[tick["code"]] = tick

    def get(self, code: str):
        return self.cache.get(code)

    # ------------------------------------------------------------------
    # V2.3 Tick 数据流：push 追加 tick，latest 取最近 n 条。
    # ------------------------------------------------------------------
    def push(self, tick: dict) -> None:
        """追加一条 tick（自动打时间戳）。"""
        tick["time"] = datetime.now()
        self.ticks.append(tick)

    def latest(self, n: int = 100) -> list:
        """取最近 n 条 tick。"""
        return self.ticks[-n:]
