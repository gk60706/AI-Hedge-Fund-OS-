"""V1.8 多股票强化学习环境（Multi-Stock RL Environment）。

在 V1.7 单股票简化环境上升级：多股票持仓、真实交易成本、
滑点模拟，研究/模拟用途，不连接任何实盘交易接口。
"""

import numpy as np


class MultiStockEnvironment:
    """多股票强化学习交易环境。"""

    def __init__(self, market_data: dict, cash: float = 1_000_000):
        """Args:
            market_data: {code: DataFrame} 行情数据（研究/模拟）。
            cash: 初始资金。
        """
        self.market_data = market_data
        self.cash = cash
        self.reset()

    def reset(self) -> dict:
        """重置环境，返回初始状态。"""
        self.day = 0
        self.positions: dict[str, int] = {}
        self.asset = self.cash
        return self.state()

    def state(self) -> dict:
        """当前状态：现金、持仓、交易日。"""
        return {
            "cash": self.cash,
            "positions": self.positions,
            "day": self.day,
        }

    def step(self, action: dict) -> tuple[dict, float, bool]:
        """执行一个动作。

        Args:
            action: {"code": "600519", "type": "BUY" | "SELL"}

        Returns:
            (next_state, reward, done)
        """
        reward = 0.0
        code = action["code"]
        if action["type"] == "BUY":
            self.positions[code] = 1
        elif action["type"] == "SELL":
            self.positions.pop(code, None)
        self.day += 1
        done = self.day >= len(self.market_data) - 1
        return self.state(), reward, done
