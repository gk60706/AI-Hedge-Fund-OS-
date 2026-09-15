"""V3.9.1 core type definitions.

Note: V3.7 keeps its own ``data.point_in_time.PITRecord`` (without a ``field``
attribute) for backward compatibility. The record below is the V3.9.1
PIT record that carries the fundamental ``field`` name.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

Direction = Literal["LONG_HIGH", "LONG_LOW", "NONE"]


@dataclass(frozen=True)
class PITRecord:
    code: str
    field: str
    period_end: date
    value: float
    publish_date: date
    available_date: date


@dataclass(frozen=True)
class TradeDecision:
    code: str
    signal_date: date
    execution_date: date
    target_weight: float
