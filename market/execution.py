"""V3.9.1 market execution：100 股整数手 + 涨跌停拦截。"""
from __future__ import annotations

from dataclasses import dataclass

from market.limit_rules import is_limit_down, is_limit_up


@dataclass(frozen=True)
class ExecutionResult:
    shares: int
    price: float
    notional: float
    executed: bool
    reason: str


def execute_order(
    side: str,
    shares: int,
    price: float,
    code: str = "",
    prev_close: float = 0.0,
) -> ExecutionResult:
    """执行一笔订单（V3.9.1 简化模型）。

    - 不足 100 股整数手 → reason="lot_size"
    - BUY 且涨停 / SELL 且跌停 → blocked
    - 成功 → reason="filled"
    """
    lot = (int(shares) // 100) * 100
    if lot <= 0:
        return ExecutionResult(0, price, 0.0, False, "lot_size")
    if side == "BUY" and prev_close > 0 and code and is_limit_up(prev_close, price, code):
        return ExecutionResult(0, price, 0.0, False, "limit_up")
    if side == "SELL" and prev_close > 0 and code and is_limit_down(prev_close, price, code):
        return ExecutionResult(0, price, 0.0, False, "limit_down")
    return ExecutionResult(lot, price, float(lot) * price, True, "filled")
