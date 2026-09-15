"""V3.9.1 point-in-time tests: lookahead detection + PIT query."""
from __future__ import annotations

import pandas as pd

from data.point_in_time import V391PointInTimeStore
from validation.lookahead import find_lookahead


def test_find_lookahead_one_violation():
    panel = pd.DataFrame(
        {
            "date": ["2024-03-28", "2024-03-29", "2024-03-30"],
            "code": ["300394", "300394", "300394"],
            "available_date": [
                "2024-03-27",
                "2024-03-30",
                "2024-03-30",
            ],
        }
    )
    violations = find_lookahead(panel)
    assert len(violations) == 1
    assert violations[0] == 1


def test_pit_query_before_and_after_available():
    store = V391PointInTimeStore()
    frame = pd.DataFrame(
        [
            {
                "code": "300394",
                "field": "roe",
                "period_end": "2024-03-30",
                "value": 10,
                "publish_date": "2024-03-30",
                "available_date": "2024-03-30",
            }
        ]
    )
    store.add(frame)
    assert store.query("300394", "roe", "2024-03-29") is None
    assert store.query("300394", "roe", "2024-03-30") == 10
