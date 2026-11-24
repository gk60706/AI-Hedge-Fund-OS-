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

# ============================================================
# V3.0.5 AI Trade Review：交易复盘评分（升级版）
# ============================================================
class TradeReviewV305:
    def review(
        self,
        trade: dict,
    ) -> dict:
        pnl_pct = float(trade.get("pnl_pct", 0))
        holding_days = int(trade.get("holding_days", 0))
        score = 50
        lessons = []
        if pnl_pct >= 0.10:
            result = "EXCELLENT"
            score += 30
            lessons.append("该交易收益明显高于基础阈值")
        elif pnl_pct > 0:
            result = "WIN"
            score += 10
            lessons.append("交易产生正收益")
        elif pnl_pct <= -0.10:
            result = "BAD_LOSS"
            score -= 30
            lessons.append("出现较大亏损，需要重点复盘")
        else:
            result = "LOSS"
            score -= 10
            lessons.append("交易产生亏损")
        if holding_days > 60:
            score -= 5
            lessons.append("持仓周期较长")
        if holding_days <= 3:
            lessons.append("属于短周期交易")
        return {
            "result": result,
            "review_score": max(0, min(100, score)),
            "pnl_pct": pnl_pct,
            "holding_days": holding_days,
            "lessons": lessons,
        }

    def batch_review(
        self,
        trades: list[dict],
    ):
        return [
            self.review(trade)
            for trade in trades
        ]
