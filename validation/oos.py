"""V3.5 OOSValidator：样本外验证（Sharpe 下限 + 最大回撤上限）。"""

from __future__ import annotations


class OOSValidator:
    def evaluate(
        self,
        metrics,
        minimum_sharpe=0.8,
        maximum_drawdown=-0.25,
    ):
        if not metrics:
            return {"passed": False, "reason": "NO_METRICS"}
        sharpe = metrics.get("sharpe", 0)
        drawdown = metrics.get("max_drawdown", -1)
        if sharpe < minimum_sharpe:
            return {"passed": False, "reason": "SHARPE_TOO_LOW"}
        if drawdown < maximum_drawdown:
            return {"passed": False, "reason": "DRAWDOWN_TOO_HIGH"}
        return {"passed": True, "reason": "PASS"}
