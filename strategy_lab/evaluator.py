"""V1.1 策略评价 Agent：基于回测指标评估策略并决定保留/淘汰。"""


def evaluate(backtest):
    score = 0
    if backtest["return"] > 0.2:
        score += 50
    if backtest["drawdown"] < 0.15:
        score += 30
    if backtest["sharpe"] > 1:
        score += 20
    return {
        "score": score,
        "status": "KEEP" if score >= 80 else "DROP",
    }
