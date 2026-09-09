"""V1.5 Tick 实时数据流：内存缓存最新 Tick。"""


class TickStream:
    """Tick 数据流缓存。"""

    def __init__(self) -> None:
        self.cache = {}

    def update(self, tick: dict) -> None:
        self.cache[tick["code"]] = tick

    def get(self, code: str):
        return self.cache.get(code)
