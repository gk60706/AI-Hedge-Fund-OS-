"""V3.0.1 Real Market Data Engine：本地 JSON 缓存。

避免每个 Agent 都重复请求行情。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class DataCache:
    def __init__(
        self,
        directory: str = "data/cache",
        ttl_seconds: int = 60,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.ttl_seconds = ttl_seconds

    def _path(self, key: str) -> Path:
        safe_key = (
            key.replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
        )
        return (
            self.directory
            / f"{safe_key}.json"
        )

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.exists():
            return None
        if (
            time.time()
            - path.stat().st_mtime
            > self.ttl_seconds
        ):
            return None
        try:
            return json.loads(
                path.read_text(encoding="utf-8")
            )
        except Exception:
            return None

    def set(self, key: str, value: dict[str, Any]):
        path = self._path(key)
        path.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )


# ============================================================================
# V3.9.1 unified research engine - simple CSV cache
# ============================================================================


class CSVCache:
    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = Path(cache_dir)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe}.csv"

    def get(self, key: str):
        path = self._path(key)
        if not path.exists():
            return None
        return pd.read_csv(path, parse_dates=["date"])

    def put(self, key: str, df) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(self._path(key), index=False)
import pandas as pd
