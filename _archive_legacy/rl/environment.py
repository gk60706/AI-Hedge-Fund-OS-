"""V1.7 强化学习交易环境（简化全仓模拟，无真实交易）。"""

import numpy as np

from rl.action import Action


class TradingEnvironment:
    """简化交易环境。"""

    def __init__(self, prices, features, initial_cash=1_000_000):
        self.prices = np.asarray(prices, dtype=float)
        self.features = np.asarray(features, dtype=float)
        self.initial_cash = initial_cash
        self.reset()

    def reset(self):
        self.step_index = 0
        self.cash = self.initial_cash
        self.position = 0.0
        self.prev_value = self.initial_cash
        return self._state()

    def portfolio_value(self):
        price = self.prices[self.step_index]
        return self.cash + self.position * price

    def _state(self):
        return np.concatenate(
            [
                self.features[self.step_index],
                np.array(
                    [self.position, self.cash / self.initial_cash],
                    dtype=float,
                ),
            ]
        ).astype(np.float32)

    def step(self, action):
        current_price = self.prices[self.step_index]
        # 简化的全仓交易环境
        if action == Action.BUY:
            if self.cash > 0:
                self.position += self.cash / current_price
                self.cash = 0
        elif action == Action.SELL:
            if self.position > 0:
                self.cash += self.position * current_price
                self.position = 0
        self.step_index += 1
        done = self.step_index >= len(self.prices) - 1
        new_value = self.portfolio_value()
        reward = new_value / self.prev_value - 1
        self.prev_value = new_value
        return (
            self._state(),
            float(reward),
            done,
            {"portfolio_value": new_value},
        )
