"""V3.5 PerformanceMetrics：组合绩效指标（总收益 / CAGR / 年化波动 / Sharpe / Sortino / 最大回撤 / Calmar / 胜率 / 盈亏比）。"""

from __future__ import annotations

import numpy as np


class PerformanceMetrics:
    """根据净值曲线计算一套完整的基金绩效指标。

    指标口径：
    - total_return    : 累计收益率 equity[-1]/equity[0]-1
    - cagr            : 年化复合收益 (equity[-1]/equity[0])**(1/years)-1
    - annual_volatility: 年化波动率 returns.std(ddof=1)*sqrt(periods)
    - sharpe          : 年化夏普 returns.mean()/returns.std(ddof=1)*sqrt(periods)
    - sortino         : 下行风险调整收益 cagr / 下行波动
    - max_drawdown    : 最大回撤 min(equity/cummax(equity)-1)
    - calmar          : cagr / abs(max_drawdown)
    - win_rate        : 盈利周期占比
    - profit_factor   : 总盈利 / 总亏损绝对值
    - final_equity    : 期末净值
    """

    def calculate(
        self,
        equity_curve,
        periods_per_year: int = 252,
    ) -> dict:
        equity = np.asarray(equity_curve, dtype=float)
        if len(equity) < 2:
            return {}
        returns = equity[1:] / equity[:-1] - 1

        total_return = equity[-1] / equity[0] - 1
        periods = len(returns)
        years = periods / periods_per_year
        if years > 0:
            cagr = (equity[-1] / equity[0]) ** (1 / years) - 1
        else:
            cagr = 0.0

        annual_volatility = returns.std(ddof=1) * np.sqrt(periods_per_year)
        if annual_volatility > 0:
            sharpe = returns.mean() / returns.std(ddof=1) * np.sqrt(periods_per_year)
        else:
            sharpe = 0.0

        downside = returns[returns < 0]
        if len(downside) > 1:
            downside_vol = downside.std(ddof=1) * np.sqrt(periods_per_year)
            sortino = cagr / max(downside_vol, 1e-8)
        else:
            sortino = 0.0

        peak = np.maximum.accumulate(equity)
        drawdown = equity / peak - 1
        max_drawdown = drawdown.min()
        if max_drawdown < 0:
            calmar = cagr / abs(max_drawdown)
        else:
            calmar = 0.0

        winning = returns[returns > 0]
        losing = returns[returns < 0]
        win_rate = len(winning) / len(returns) if len(returns) else 0.0
        gross_profit = winning.sum()
        gross_loss = abs(losing.sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        return {
            "total_return": float(total_return),
            "cagr": float(cagr),
            "annual_volatility": float(annual_volatility),
            "sharpe": float(sharpe),
            "sortino": float(sortino),
            "max_drawdown": float(max_drawdown),
            "calmar": float(calmar),
            "win_rate": float(win_rate),
            "profit_factor": float(profit_factor),
            "final_equity": float(equity[-1]),
        }
