"""V3.5 OOSValidator：样本外验证（Sharpe 下限 + 最大回撤上限）。"""

from __future__ import annotations
import pandas as pd


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
# ============================================================================
# V3.9.1 unified research engine - OOS evaluation (dump)
# ============================================================================


def evaluate_oos(expression, oos: pd.DataFrame, horizon: int = 1):
    work = oos.copy().sort_values(["date", "code"]).reset_index(drop=True)
    signal = ExpressionEvaluator().evaluate(expression, work)
    future_return = work.groupby("code")["close"].shift(-horizon) / work["close"] - 1
    ic_series = cross_sectional_ic(signal, future_return, work["date"])
    return {
        "oos_ic": mean_ic(ic_series),
        "oos_positive_ratio": (
            float((ic_series.dropna() > 0).mean())
            if ic_series.notna().any()
            else float("nan")
        ),
        "oos_days": int(ic_series.notna().sum()),
    }


from alpha.evaluator import ExpressionEvaluator  # noqa: E402
from alpha.ic import cross_sectional_ic, mean_ic  # noqa: E402
