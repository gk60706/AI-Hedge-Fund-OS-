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
