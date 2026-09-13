"""V3.0.4 Paper Trading 完整账本：记录每笔模拟交易。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class TradeLedger:
    def __init__(
        self,
        path: str = "data/trade_ledger.json",
    ):
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.trades: list[dict[str, Any]] = self._load()

    def _load(self):
        if not self.path.exists():
            return []
        try:
            return json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except Exception:
            return []

    def append(self, trade: dict[str, Any]):
        trade = dict(trade)
        trade.setdefault(
            "timestamp",
            datetime.now().isoformat(timespec="seconds"),
        )
        trade.setdefault(
            "trade_id",
            f"T{len(self.trades) + 1:08d}",
        )
        self.trades.append(trade)
        self._save()

    def _save(self):
        self.path.write_text(
            json.dumps(
                self.trades,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    def all(self):
        return list(self.trades)

    def last(self, n: int = 20):
        return self.trades[-n:]
