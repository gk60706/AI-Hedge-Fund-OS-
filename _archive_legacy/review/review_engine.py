"""V3.0.5 AI 复盘统计器：聚合 TradeReview 结果。"""
from __future__ import annotations

from typing import Any


class ReviewEngine:
    def analyze(
        self,
        reviews: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not reviews:
            return {
                "count": 0,
                "win_rate": 0,
                "avg_pnl": 0,
                "avg_score": 0,
            }
        count = len(reviews)
        wins = sum(
            1
            for item in reviews
            if item["pnl_pct"] > 0
        )
        avg_pnl = (
            sum(item["pnl_pct"] for item in reviews)
            / count
        )
        avg_score = (
            sum(item["review_score"] for item in reviews)
            / count
        )
        return {
            "count": count,
            "win_rate": wins / count,
            "avg_pnl": avg_pnl,
            "avg_score": avg_score,
        }
