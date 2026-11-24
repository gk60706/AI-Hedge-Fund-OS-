"""V3.0 AI Autonomous Hedge Fund：组合账户。"""
from __future__ import annotations

from typing import Any

from portfolio.position import PositionV30 as Position


class PortfolioV30:
    def __init__(
        self,
        initial_cash: float = 1_000_000,
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.trade_history: list[dict[str, Any]] = []

    @property
    def market_value(self) -> float:
        return sum(
            position.market_value
            for position in self.positions.values()
        )

    @property
    def total_value(self) -> float:
        return (
            self.cash
            + self.market_value
        )

    @property
    def pnl(self) -> float:
        return (
            self.total_value
            - self.initial_cash
        )

    @property
    def return_pct(self) -> float:
        return (
            self.total_value
            / self.initial_cash
            - 1
        )

    def update_prices(
        self,
        prices: dict[str, float],
    ):
        for code, price in prices.items():
            if code in self.positions:
                self.positions[code].current_price = price

    def add_position(
        self,
        position: Position,
    ):
        self.positions[position.code] = position

    def remove_position(
        self,
        code: str,
    ):
        if code in self.positions:
            del self.positions[code]

    def snapshot(self) -> dict:
        return {
            "cash": self.cash,
            "market_value": self.market_value,
            "total_value": self.total_value,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
            "positions": {
                code: {
                    "shares": position.shares,
                    "avg_price": position.avg_price,
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "pnl": position.pnl,
                    "pnl_pct": position.pnl_pct,
                }
                for code, position in self.positions.items()
            },
        }
