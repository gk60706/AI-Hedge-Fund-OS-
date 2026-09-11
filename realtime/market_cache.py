"""V2.3 Redis 实时行情缓存：行情 → Redis → AI Agent。"""

import json

import redis


class MarketCache:
    """Redis 行情缓存（localhost:6379）。"""

    def __init__(self):
        self.redis = redis.Redis(host="localhost", port=6379)

    def save(self, code: str, data: dict) -> None:
        """缓存一条行情。"""
        self.redis.set(code, json.dumps(data))

    def get(self, code: str):
        """读取缓存行情，不存在返回 None。"""
        data = self.redis.get(code)
        if data:
            return json.loads(data)
        return None
