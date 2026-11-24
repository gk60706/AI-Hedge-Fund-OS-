"""V1.1 策略评价 Agent：基于回测指标评估策略并决定保留/淘汰。"""


def evaluate(backtest):
    score = 0
    if backtest["return"] > 0.2:
        score += 50
    if backtest["drawdown"] < 0.15:
        score += 30
    if backtest["sharpe"] > 1:
        score += 20
    return {
        "score": score,
        "status": "KEEP" if score >= 80 else "DROP",
    }


class StrategyEvaluator:
    """V2.8 框架演示版：写死指标评价策略。"""

    def evaluate(self, strategy):
        result = {
            "return": 0.25,
            "sharpe": 1.8,
            "drawdown": -0.08,
        }
        score = (
            result["return"] * 0.5
            + result["sharpe"] * 0.3
            + result["drawdown"] * -0.2
        )
        result["score"] = score
        return result


class StrategyEvaluatorV281:
    """V2.8.1 可运行版：基于真实权益曲线计算 CAGR/Sharpe/Sortino/回撤/Calmar。"""

    def evaluate(self, equity_curve):
        import numpy as np
        equity = np.asarray(equity_curve, dtype=float)
        if len(equity) < 2:
            return {"score": -999}
        returns = (equity[1:] / equity[:-1] - 1)
        total_return = (equity[-1] / equity[0] - 1)
        years = len(equity) / 252
        cagr = ((equity[-1] / equity[0]) ** (1 / max(years, 1 / 252)) - 1)
        volatility = returns.std()
        if volatility > 0:
            sharpe = (returns.mean() / volatility) * np.sqrt(252)
        else:
            sharpe = 0
        downside = returns[returns < 0]
        if len(downside) > 0:
            downside_std = downside.std()
            sortino = (returns.mean() / max(downside_std, 1e-8)) * np.sqrt(252)
        else:
            sortino = 0
        peak = np.maximum.accumulate(equity)
        drawdown = (equity / peak - 1)
        max_drawdown = drawdown.min()
        calmar = (cagr / abs(max_drawdown) if max_drawdown < 0 else 0)
        score = (
            cagr * 0.30
            + sharpe * 0.25
            + sortino * 0.15
            + calmar * 0.15
            + total_return * 0.15
        )
        return {
            "total_return": float(total_return),
            "cagr": float(cagr),
            "sharpe": float(sharpe),
            "sortino": float(sortino),
            "max_drawdown": float(max_drawdown),
            "calmar": float(calmar),
            "score": float(score),
        }
