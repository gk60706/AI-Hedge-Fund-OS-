"""V2.8/V2.8.1 策略生命周期管理。

V2.8 版：StrategyLifecycle（check：KILL / PROMOTE / TEST）
V2.8.1 版：StrategyLifecycleV281（evaluate：EXPERIMENT / BACKTEST / VALIDATION / RETIRED）
"""


class StrategyLifecycle:
    """V2.8 框架演示版。"""

    def check(self, performance):
        if performance["drawdown"] < -0.2:
            return "KILL"
        if performance["sharpe"] > 2:
            return "PROMOTE"
        return "TEST"


class StrategyLifecycleV281:
    """V2.8.1 可运行版：根据回测指标判定策略生命周期状态。"""

    def evaluate(self, strategy):
        metrics = strategy.metrics
        if not metrics:
            return "EXPERIMENT"
        if metrics["max_drawdown"] < -0.20:
            return "RETIRED"
        if (metrics["sharpe"] >= 1.5 and metrics["max_drawdown"] >= -0.15):
            return "VALIDATION"
        return "BACKTEST"
