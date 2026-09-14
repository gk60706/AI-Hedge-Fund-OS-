"""V3.5 PortfolioComparison：组合与基准对比（收益 / CAGR / Sharpe / 回撤差值）。"""

from __future__ import annotations


class PortfolioComparison:
    def compare(self, portfolio_metrics, benchmark_metrics):
        return {
            "return_difference": portfolio_metrics.get("total_return", 0)
            - benchmark_metrics.get("total_return", 0),
            "cagr_difference": portfolio_metrics.get("cagr", 0)
            - benchmark_metrics.get("cagr", 0),
            "sharpe_difference": portfolio_metrics.get("sharpe", 0)
            - benchmark_metrics.get("sharpe", 0),
            "drawdown_difference": portfolio_metrics.get("max_drawdown", 0)
            - benchmark_metrics.get("max_drawdown", 0),
        }
