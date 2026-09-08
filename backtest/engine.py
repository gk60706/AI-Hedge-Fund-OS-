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
