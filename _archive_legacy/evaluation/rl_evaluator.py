"""V1.7 RL 模型评价器。"""

import numpy as np


class RLEvaluator:
    """RL 模型评价。"""

    def evaluate(self, equity_curve) -> dict:
        equity = np.asarray(equity_curve, dtype=float)
        returns = equity[1:] / equity[:-1] - 1
        total_return = equity[-1] / equity[0] - 1
        peak = np.maximum.accumulate(equity)
        drawdown = equity / peak - 1
        max_drawdown = drawdown.min()
        volatility = returns.std()
        sharpe = 0.0
        if volatility > 0:
            sharpe = (returns.mean() / volatility) * np.sqrt(252)
        return {
            "total_return": float(total_return),
            "max_drawdown": float(max_drawdown),
            "sharpe": float(sharpe),
        }
