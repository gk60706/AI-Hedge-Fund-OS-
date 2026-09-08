"""实时行情 WebSocket 客户端 (V0.8)

连接行情 WebSocket（当前为模拟占位地址，实盘时替换为券商/QMT 行情源）。
"""
import asyncio
import json

import websockets


class MarketWebSocket:
    """市场行情 WebSocket 客户端。"""

    def __init__(self, url: str = "wss://example.market.com"):
        self.url = url
        self.callbacks = []

    def register(self, callback) -> None:
        """注册行情回调。"""
        self.callbacks.append(callback)

    async def connect(self) -> None:
        """连接行情源并分发 tick。"""
        async with websockets.connect(self.url) as ws:
            while True:
                data = await ws.recv()
                tick = json.loads(data)
                for cb in self.callbacks:
                    cb(tick)
