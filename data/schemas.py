"""V3.0.1 Real Market Data Engine：行情数据 Schema。"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class StockQuote:
    code: str
    name: str
    latest_price: float | None = None
    change_pct: float | None = None
    change_amount: float | None = None
    volume: float | None = None
    amount: float | None = None
    amplitude: float | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    prev_close: float | None = None
    turnover: float | None = None
    pe: float | None = None
    pb: float | None = None
    market_cap: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
