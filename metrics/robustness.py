"""V3.5 策略可信度判断：Strategy Robustness Score（0-100）。

评分构成（满分 100）：
- Sharpe        min(sharpe/2.0, 1.0) * 25
- Sortino       min(sortino/2.5, 1.0) * 20
- Calmar        min(calmar/2.0, 1.0) * 20
- ProfitFactor  min(profit_factor/2.0, 1.0) * 15
- MaxDrawdown   max(0, 1 + max_drawdown) * 20

评级：80-100 EXCELLENT / 65-80 GOOD / 50-65 WATCH / 35-50 WEAK / <35 RETIRE
可直接与 V2.8 Strategy Evolution 对接。
"""

from __future__ import annotations


def robustness_score(metrics: dict) -> float:
    score = 0.0
    score += min(metrics["sharpe"] / 2.0, 1.0) * 25
    score += min(metrics["sortino"] / 2.5, 1.0) * 20
    score += min(metrics["calmar"] / 2.0, 1.0) * 20
    score += min(metrics["profit_factor"] / 2.0, 1.0) * 15
    score += max(0, 1 + metrics["max_drawdown"]) * 20
    return score


def robustness_grade(score: float) -> str:
    if score >= 80:
        return "EXCELLENT"
    if score >= 65:
        return "GOOD"
    if score >= 50:
        return "WATCH"
    if score >= 35:
        return "WEAK"
    return "RETIRE"
