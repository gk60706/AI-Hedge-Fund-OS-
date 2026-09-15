"""回测指标 (V0.5)

最大回撤与夏普比率（基于 NumPy）。
"""
import numpy as np


def max_drawdown(values) -> float:
    """计算净值序列的最大回撤（0-1，越大回撤越深）。

    :param values: 净值序列（iterable of float）
    """
    peak = values[0]
    max_dd = 0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return max_dd


def sharpe(returns) -> float:
    """计算收益序列的夏普比率（简化版，无风险利率取 0）。

    :param returns: 收益率序列（iterable of float）
    """
    return np.mean(returns) / np.std(returns)


def evaluate(result: dict) -> dict:
    """V1.2 回测评价：按收益率对回测结果评分。

    :param result: 含 ``return`` 键的回测结果 dict
    :return: ``{"return": float, "score": int}``，score 0-100
    """
    score = 0
    ret = result["return"]
    if ret > 0.2:
        score += 50
    elif ret > 0.1:
        score += 30
    if ret < 0:
        score -= 50
    return {"return": ret, "score": score}
# ============================================================================
# V3.9.1 unified research engine - performance metrics (equity series, dump)
# ============================================================================


def performance_metrics(equity: pd.Series):
    equity = equity.dropna().sort_index()
    if len(equity) < 2:
        return {}
    returns = equity.pct_change().dropna()
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    days = (equity.index[-1] - equity.index[0]).days
    years = max(days / 365.25, 1 / 365.25)
    if (1 + total_return) > 0:
        cagr = (1 + total_return) ** (1 / years) - 1
    else:
        cagr = -1.0
    volatility = returns.std(ddof=1) * np.sqrt(252)
    if returns.std(ddof=1) > 0:
        sharpe = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
    else:
        sharpe = np.nan
    downside = returns[returns < 0].std(ddof=1) * np.sqrt(252)
    if downside and downside > 0:
        sortino = returns.mean() * 252 / downside
    else:
        sortino = np.nan
    drawdown = equity / equity.cummax() - 1
    max_drawdown = float(drawdown.min())
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else np.nan
    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "annual_vol": float(volatility),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": max_drawdown,
        "calmar": float(calmar),
    }


import numpy as np  # noqa: E402
