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



# ============================================================================
# V3.9.1 unified research engine - survivorship / universe validation
# ============================================================================


def validate_universe(panel: pd.DataFrame) -> list[str]:
    """幸存者偏差检查：检查 panel 中 code 是否在 date 之前上市/之后退市。
    需要 lifecycle 信息时调用 HistoricalUniverse.filter；此处仅做基本检查。"""
    errors: list[str] = []
    if panel is None or panel.empty:
        return errors
    if "code" not in panel.columns:
        errors.append("panel 缺少 code 列")
    return errors
