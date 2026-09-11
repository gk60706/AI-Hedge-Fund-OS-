"""V1.8 绩效评价系统：收益 / Sharpe / 最大回撤。"""

import numpy as np


class Performance:
    """基于净值曲线计算策略绩效。"""

    def analyze(self, equity) -> dict:
        """计算总收益、年化 Sharpe、最大回撤。

        Args:
            equity: 净值序列。

        Returns:
            {"return": ..., "sharpe": ..., "max_drawdown": ...}
        """
        equity = np.asarray(equity, dtype=float)
        returns = equity[1:] / equity[:-1] - 1
        total = equity[-1] / equity[0] - 1
        std = returns.std()
        sharpe = (returns.mean() / std * np.sqrt(252)) if std > 0 else 0.0
        peak = np.maximum.accumulate(equity)
        drawdown = equity / peak - 1
        return {
            "return": total,
            "sharpe": sharpe,
            "max_drawdown": drawdown.min(),
        }
