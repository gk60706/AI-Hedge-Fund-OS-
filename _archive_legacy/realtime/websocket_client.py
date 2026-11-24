"""实时行情 WebSocket 客户端 (V0.8)

连接行情 WebSocket（当前为模拟占位地址，实盘时替换为券商/QMT 行情源）。

V2.3 追加：MarketWebSocketV23（同步 websocket-client 版，subscribe 订阅模式）。
"""
import asyncio
import json

import websockets


class MarketWebSocket:
    """市场行情 WebSocket 客户端（V0.8 异步版）。"""

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


# ---------------------------------------------------------------------------
# V2.3 实时行情 WebSocket 模块（同步 websocket-client 版）。
# ---------------------------------------------------------------------------
import websocket as _ws  # websocket-client


class MarketWebSocketV23:
    """V2.3 市场行情 WebSocket 客户端（同步版）。"""

    def __init__(self, url):
        self.url = url

    def connect(self):
        """建立 WebSocket 连接，返回连接对象。"""
        ws = _ws.WebSocket()
        ws.connect(self.url)
        return ws

    def subscribe(self, ws, symbols) -> None:
        """订阅股票代码列表。"""
        message = {"type": "subscribe", "symbols": symbols}
        ws.send(json.dumps(message))
