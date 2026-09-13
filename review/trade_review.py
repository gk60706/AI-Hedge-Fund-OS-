"""V3.0 AI Autonomous Hedge Fund：AI 交易复盘。"""
from __future__ import annotations

from typing import Any


class TradeReviewV30:
    def review(
        self,
        trade: dict[str, Any],
    ) -> dict[str, Any]:
        pnl_pct = float(
            trade.get("pnl_pct", 0)
        )
        holding_days = int(
            trade.get("holding_days", 0)
        )
        if pnl_pct > 0.10:
            result = "WIN"
        elif pnl_pct < -0.05:
            result = "LOSS"
        else:
            result = "NEUTRAL"
        lessons = []
        if result == "LOSS":
            lessons.append("检查买入时机")
            lessons.append("检查止损纪律")
        if holding_days > 60:
            lessons.append("检查策略持仓周期")
        return {
            "result": result,
            "pnl_pct": pnl_pct,
            "holding_days": holding_days,
            "lessons": lessons,
        }
