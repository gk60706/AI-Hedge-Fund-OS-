from __future__ import annotations

from datetime import date

from data.universe import (
    HistoricalUniverse,
)


class SurvivorshipDetector:
    def __init__(
        self,
        universe: HistoricalUniverse,
    ):
        self.universe = universe

    def validate(
        self,
        codes: list[str],
        as_of_date: date,
    ):
        missing = []
        for code in codes:
            if not self.universe.is_active(
                code,
                as_of_date,
            ):
                missing.append(code)
        return {
            "valid": len(missing) == 0,
            "invalid_codes": missing,
        }
