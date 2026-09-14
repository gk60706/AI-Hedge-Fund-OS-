from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


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
