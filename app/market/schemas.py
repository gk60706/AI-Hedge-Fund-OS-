"""行情接口的请求/响应模型。"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class HistoryBar(BaseModel):
    """单根日 K 线。"""

    date: date
    open: float
    close: float
    high: float
    low: float
    volume: int
    amount: float
    pct_change: float | None = None


class HistoryResponse(BaseModel):
    """历史行情响应。"""

    symbol: str
    adjust: str = "qfq"
    total: int = 0
    bars: list[HistoryBar] = Field(default_factory=list)


class QuoteResponse(BaseModel):
    """实时快照行情响应。"""

    symbol: str
    name: str | None = None
    price: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    amount: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
