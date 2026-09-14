from __future__ import annotations

from datetime import date

from data.universe import (
    HistoricalUniverse,
)
from validation.survivorship import (
    SurvivorshipDetector,
)


class BacktestAudit:
    def __init__(
        self,
        universe: HistoricalUniverse,
    ):
        self.universe = universe

    def audit_universe(
        self,
        codes: list[str],
        as_of_date: date,
    ):
        detector = (
            SurvivorshipDetector(
                self.universe
            )
        )
        return detector.validate(
            codes,
            as_of_date,
        )

    def final_report(
        self,
        universe_result,
        lookahead_result=None,
        leakage_result=None,
    ):
        passed = (
            universe_result["valid"]
            and (
                lookahead_result is None
                or lookahead_result["valid"]
            )
            and (
                leakage_result is None
                or leakage_result["valid"]
            )
        )
        return {
            "passed": passed,
            "universe": universe_result,
            "lookahead": (lookahead_result),
            "leakage": (leakage_result),
        }
