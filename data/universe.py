from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SecurityLifecycle:
    code: str
    ipo_date: date
    delist_date: date | None = None
    name: str = ""


class HistoricalUniverse:
    def __init__(self):
        self.securities: dict[str, SecurityLifecycle] = {}

    def add(self, security: SecurityLifecycle,):
        self.securities[security.code] = security

    def is_active(self, code: str, as_of_date: date,) -> bool:
        security = self.securities.get(code)
        if security is None:
            return False
        if as_of_date < security.ipo_date:
            return False
        if (
            security.delist_date is not None
            and as_of_date >= security.delist_date
        ):
            return False
        return True

    def active_codes(self, as_of_date: date,) -> list[str]:
        return [
            code
            for code in self.securities
            if self.is_active(code, as_of_date,)
        ]
