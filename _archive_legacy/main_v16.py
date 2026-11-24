"""V1.6 机器学习交易引擎入口：多模型融合 → AI 交易信号。

研究/模拟用途，只输出决策信号，不接入任何真实交易通道。
"""

from intraday.ml_trader import MLTrader
from prediction.ensemble import EnsemblePredictor


def main() -> None:
    ensemble = EnsemblePredictor()
    result = ensemble.predict(xgb=0.82, lstm=0.75, transformer=0.80)
    print("AI预测:")
    print(result)

    trader = MLTrader()
    decision = trader.decide(result)
    print("交易决定:")
    print(decision)


if __name__ == "__main__":
    main()
