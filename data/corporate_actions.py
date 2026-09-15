from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CorporateAction:
    code: str
    ex_date: date
    action_type: str
    cash_dividend: float = 0.0
    split_factor: float = 1.0


class CorporateActionStore:
    def __init__(self):
        self.actions: list[CorporateAction] = []

    def add(self, action: CorporateAction,):
        self.actions.append(action)

    def query(self, code: str, as_of_date: date,):
        return [
            action
            for action in self.actions
            if action.code == code
            and action.ex_date <= as_of_date
        ]


# ============================================================================
# V3.9.1 unified research engine - corporate action factor
# ============================================================================


class CorporateActionStoreV391:
    def __init__(self):
        self.records = []

    def add(self, record) -> None:
        self.records.append(record)

    def factor_on(self, code: str, date, factor: float = 1.0) -> float:
        total = 1.0
        for record in self.records:
            if getattr(record, "code", None) == code:
                ex_date = getattr(record, "ex_date", None)
                if ex_date is not None and str(ex_date) <= str(date):
                    total *= factor
        return total
