"""V3.0.4 账户统计：生成组合的完整报表。"""
from __future__ import annotations

from typing import Any


class AccountReport:
    def generate(self, portfolio) -> dict[str, Any]:
        positions = []
        for position in portfolio.positions.values():
            positions.append({
                "code": position.code,
                "name": position.name,
                "shares": position.shares,
                "avg_price": position.avg_price,
                "current_price": position.current_price,
                "market_value": position.market_value,
                "pnl": position.pnl,
                "pnl_pct": position.pnl_pct,
            })
        return {
            "cash": portfolio.cash,
            "market_value": portfolio.market_value,
            "total_value": portfolio.total_value,
            "pnl": portfolio.pnl,
            "return_pct": portfolio.return_pct,
            "positions": positions,
            "trade_count": len(portfolio.trade_history),
        }
