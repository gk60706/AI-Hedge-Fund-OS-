from __future__ import annotations

import tempfile
from pathlib import Path

from . import signal_ledger


def _sample(as_of: str = "2026-11-20") -> dict:
    return {
        "quality_filter": True,
        "daily_top_k": 2,
        "conditions": ["above_ma20"],
        "match_mode": "at_least",
        "top_picks": [
            {
                "symbol": "600519.SH",
                "name": "贵州茅台",
                "score": 88,
                "quality_score": 97,
                "signal_status": "新信号",
                "fresh_signal": True,
                "as_of": as_of,
                "matched": ["above_ma20"],
                "quality": {"grade": "A", "metrics": {"vol_ratio_20_prev": 1.5}},
            },
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "score": 72,
                "quality_score": 80,
                "signal_status": "持续合格",
                "fresh_signal": False,
                "as_of": as_of,
                "matched": [],
                "quality": {"grade": "B", "metrics": {}},
            },
        ],
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        signal_ledger.LEDGER_PATH = Path(tmp) / "ledger.sqlite"
        first = signal_ledger.record_top_picks(_sample(), universe="hs300")
        assert first == 2, first
        second = signal_ledger.record_top_picks(_sample(), universe="hs300")
        assert second == 0, second
        data = signal_ledger.recent(days=30, limit=10)
        assert data["summary"]["total"] == 2, data["summary"]
        assert data["summary"]["days"] == 1
        assert data["summary"]["fresh"] == 1
        assert len(data["items"]) == 2
        assert data["items"][0]["top_rank"] == 1
        print("ledger tests: PASS")


if __name__ == "__main__":
    main()
