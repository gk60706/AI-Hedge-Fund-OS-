"""自动策略搜索 (V0.5)

基于 Optuna 的参数搜索接口（示例：动量周期 + 买入阈值）。
"""
import optuna


def objective(trial) -> float:
    """Optuna 目标函数（示例实现，接入真实回测后替换评分逻辑）。"""
    period = trial.suggest_int("period", 5, 120)
    threshold = trial.suggest_int("threshold", 50, 90)
    # 接真实回测结果
    score = period * 0.1 + threshold * 0.1
    return score


def optimize() -> dict:
    """运行参数搜索，返回最优参数。"""
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=100)
    return study.best_params
