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
# ============================================================================
# V3.9.1 unified research engine - full audit (dump)
# ============================================================================


def full_audit(df, target_col=None):
    result = {
        "data_quality": audit_panel(df),
        "lookahead_rows": int(len(find_lookahead(df))),
    }
    if target_col:
        result["leakage"] = leakage_checks(df, target_col)
    else:
        result["leakage"] = []
    return result


from validation.data_quality import audit_panel  # noqa: E402
from validation.leakage import leakage_checks  # noqa: E402
from validation.lookahead import find_lookahead  # noqa: E402
