"""回测引擎 (V0.5)

封装 Backtrader Cerebro 的简单回测入口，返回收益摘要。
"""
import backtrader as bt

from backtest.strategy import AlphaStrategy


def run_backtest(data) -> dict:
    """运行一次回测。

    :param data: Backtrader 数据源（``bt.feeds.*`` 或 pandas 转换）
    :return: ``{"initial": ..., "final": ..., "return": ...}``
    """
    cerebro = bt.Cerebro()
    cerebro.addstrategy(AlphaStrategy)
    cerebro.adddata(data)
    cerebro.broker.setcash(100000)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)
    cerebro.run()
    final = cerebro.broker.getvalue()
    return {
        "initial": 100000,
        "final": final,
        "return": (final / 100000 - 1),
    }


class BacktestEngine:
    """V1.2 回测引擎（升级版）：基于 pandas 逐行模拟。

    与 V0.5 的 ``run_backtest``（Backtrader）并存，不删除已有功能。
    用于 AI 自动回测：逐行调用策略函数，按 BUY/SELL 信号切换仓位。
    """

    def __init__(self, initial_capital: float = 1000000) -> None:
        self.initial_capital = initial_capital

    def run(self, data, strategy) -> dict:
        """运行一次逐行回测。

        :param data: 含 ``price`` 列的 DataFrame
        :param strategy: 可调用对象，接收一行数据，返回
                         ``"BUY"`` / ``"SELL"`` / 其它（不动作）
        :return: ``{"capital": float, "return": float}``
        """
        capital = float(self.initial_capital)
        position = 0
        for _, row in data.iterrows():
            signal = strategy(row)
            if signal == "BUY":
                position = capital / row["price"]
            elif signal == "SELL":
                capital = position * row["price"]
                position = 0
        # 收尾：仍持有仓位时按最后价格结算
        if position > 0:
            capital = position * data.iloc[-1]["price"]
            position = 0
        return {
            "capital": capital,
            "return": capital / self.initial_capital - 1,
        }


class BacktestEngineV281:
    """V2.8.1 可运行版回测引擎：价格序列 + 信号序列 → 权益曲线。

    支持佣金与滑点，BUY 全仓买入、SELL 全仓卖出，返回 numpy 权益曲线。
    """

    def run(self, prices, signals, initial_cash=1_000_000, commission=0.0003, slippage=0.0005):
        import numpy as np
        prices = np.asarray(prices, dtype=float)
        signals = np.asarray(signals, dtype=int)
        cash = initial_cash
        shares = 0
        equity_curve = []
        for i in range(len(prices)):
            price = prices[i]
            signal = signals[i]
            # BUY
            if signal == 1 and shares == 0:
                execution_price = price * (1 + slippage)
                available_cash = cash
                shares = int(available_cash / execution_price / 100) * 100
                cost = shares * execution_price
                fee = cost * commission
                cash -= (cost + fee)
            # SELL
            elif signal == -1 and shares > 0:
                execution_price = price * (1 - slippage)
                revenue = shares * execution_price
                fee = revenue * commission
                cash += (revenue - fee)
                shares = 0
            equity = cash + shares * price
            equity_curve.append(equity)
        return np.asarray(equity_curve)
