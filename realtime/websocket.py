"""V1.5 WebSocket 实时行情：订阅推送并分发 Tick。"""

import asyncio
import json

import websockets


class StockWebSocket:
    """WebSocket 行情客户端（实时 Tick 订阅分发）。"""

    def __init__(self, url: str) -> None:
        self.url = url
        self.handlers = []

    def subscribe(self, handler) -> None:
        """注册 Tick 处理函数。"""
        self.handlers.append(handler)

    async def start(self) -> None:
        """连接行情源并持续分发消息。"""
        async with websockets.connect(self.url) as ws:
            while True:
                msg = await ws.recv()
                tick = json.loads(msg)
                for handler in self.handlers:
                    handler(tick)
