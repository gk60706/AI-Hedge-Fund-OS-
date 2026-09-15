from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PITRecord:
    code: str
    period_end: date
    value: Any
    publish_date: date
    available_date: date | None = None

    def effective_date(self) -> date:
        if self.available_date is not None:
            return self.available_date
        return self.publish_date


class PointInTimeStore:
    def __init__(self):
        self.records: list[PITRecord] = []

    def add(self, record: PITRecord,):
        self.records.append(record)

    def query(self, code: str, as_of_date: date,):
        candidates = [
            record
            for record in self.records
            if record.code == code
            and record.effective_date() <= as_of_date
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda x: (
                x.period_end,
                x.effective_date(),
            )
        )
        return candidates[-1]

    def query_many(self, code: str, as_of_date: date,):
        return [
            record
            for record in self.records
            if record.code == code
            and record.effective_date() <= as_of_date
        ]


# ============================================================================
# V3.9.1 unified research engine - DataFrame point-in-time store
# ============================================================================

PIT_REQUIRED_COLUMNS = [
    "code",
    "field",
    "period_end",
    "value",
    "publish_date",
    "available_date",
]


class V391PointInTimeStore:
    def __init__(self, records=None):
        if records is None:
            self.records = pd.DataFrame(columns=PIT_REQUIRED_COLUMNS)
        else:
            self.records = records.copy()

    def add(self, frame: pd.DataFrame) -> None:
        missing = [
            c for c in PIT_REQUIRED_COLUMNS if c not in frame.columns
        ]
        if missing:
            raise ValueError(f"PIT DataFrame 缺少字段: {missing}")
        self.records = pd.concat(
            [self.records, frame[PIT_REQUIRED_COLUMNS]],
            ignore_index=True,
        )

    def query(self, code: str, field: str, as_of):
        candidates = self.records[
            (self.records["code"] == code)
            & (self.records["field"] == field)
            & (
                pd.to_datetime(self.records["available_date"])
                <= pd.Timestamp(as_of)
            )
        ]
        if candidates.empty:
            return None
        candidates = candidates.sort_values(["period_end", "available_date"])
        return float(candidates.iloc[-1]["value"])
