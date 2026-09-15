from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import pandas as pd


@dataclass(frozen=True)
class DataAvailability:
    field: str
    period_end: date
    publish_date: date
    available_date: date


class AvailabilityChecker:
    def is_available(self, item: DataAvailability, as_of_date: date,) -> bool:
        return (item.available_date <= as_of_date)

    def assert_available(self, item: DataAvailability, as_of_date: date,):
        if not self.is_available(item, as_of_date,):
            raise ValueError(
                f"未来数据泄漏: "
                f"'{item.field}'"
                f"available={item.available_date}"
                f"as_of={as_of_date}"
            )


# ============================================================================
# V3.9.1 unified research engine - availability check
# ============================================================================


def validate_availability(
    panel: pd.DataFrame,
    min_observations: int = 120,
):
    counts = panel.groupby("code").size()
    return counts[counts >= min_observations]
