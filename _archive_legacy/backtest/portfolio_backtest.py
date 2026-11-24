"""V3.5 PortfolioBacktest：组合回测核心。

逐日按目标权重调仓：
- 买入：execution_price = price * (1 + slippage)，付 commission
- 卖出：execution_price = price * (1 - slippage)，付 commission + stamp_duty
- 现金不足时按可用现金折算股数
- 输出净值曲线 / 平均换手 / 期末持仓
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class PortfolioBacktest:
    def __init__(
        self,
        initial_capital=1_000_000,
        commission=0.0003,
        stamp_duty=0.0005,
        slippage=0.0005,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.stamp_duty = stamp_duty
        self.slippage = slippage

    def run(self, prices: pd.DataFrame, target_weights: pd.DataFrame):
        dates = prices.index
        codes = prices.columns
        cash = self.initial_capital
        holdings = {code: 0.0 for code in codes}
        equity_curve = []
        turnover_history = []

        for date in dates:
            price_row = prices.loc[date]
            target_row = target_weights.loc[date] if date in target_weights.index else None
            portfolio_value = cash + sum(
                holdings[code] * price_row[code]
                for code in codes
                if np.isfinite(price_row[code])
            )
            turnover = 0.0

            # -------------------------
            # 调仓
            # -------------------------
            if target_row is not None:
                for code in codes:
                    price = price_row[code]
                    if not np.isfinite(price) or price <= 0:
                        continue
                    target_weight = float(target_row.get(code, 0.0))
                    target_value = portfolio_value * target_weight
                    current_value = holdings[code] * price
                    trade_value = target_value - current_value
                    if abs(trade_value) < 1:
                        continue

                    # 买入
                    if trade_value > 0:
                        execution_price = price * (1 + self.slippage)
                        shares = trade_value / execution_price
                        cost = shares * execution_price
                        fee = cost * self.commission
                        total_cost = cost + fee
                        if total_cost > cash:
                            shares = cash / (execution_price * (1 + self.commission))
                            cost = shares * execution_price
                            fee = cost * self.commission
                        cash -= cost + fee
                        holdings[code] += shares
                        turnover += cost
                    # 卖出
                    else:
                        shares = min(
                            holdings[code],
                            abs(trade_value) / (price * (1 - self.slippage)),
                        )
                        execution_price = price * (1 - self.slippage)
                        revenue = shares * execution_price
                        commission = revenue * self.commission
                        stamp = revenue * self.stamp_duty
                        cash += revenue - commission - stamp
                        holdings[code] -= shares
                        turnover += revenue

            # -------------------------
            # 组合净值
            # -------------------------
            equity = cash + sum(
                holdings[code] * price_row[code]
                for code in codes
                if np.isfinite(price_row[code])
            )
            equity_curve.append(equity)
            turnover_history.append(turnover / max(equity, 1))

        return {
            "equity_curve": np.asarray(equity_curve),
            "turnover": float(np.mean(turnover_history) if turnover_history else 0),
            "holdings": holdings,
        }
