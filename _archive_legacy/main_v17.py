"""V1.7 强化学习交易 Agent 入口：模拟市场 → DQN 训练 → 评价。

研究/模拟用途，仅输出训练历史与评价指标，不接入任何真实交易通道。
"""

import numpy as np

from evaluation.rl_evaluator import RLEvaluator
from rl.dqn_agent import DQNAgent
from rl.environment import TradingEnvironment
from rl.trainer import RLTrainer


def main() -> None:
    # 创建模拟市场数据
    np.random.seed(42)
    prices = [100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 500)))]
    prices = np.asarray(prices[0])
    # 7 个基础特征
    features = []
    for i in range(len(prices)):
        if i < 20:
            features.append([0] * 5)
            continue
        return_1d = prices[i] / prices[i - 1] - 1
        return_5d = prices[i] / prices[i - 5] - 1
        volatility = np.std(
            [
                prices[j] / prices[j - 1] - 1
                for j in range(i - 19, i + 1)
            ]
        )
        momentum = prices[i] / prices[i - 20] - 1
        features.append([return_1d, return_5d, volatility, 1.0, momentum])
    features = np.asarray(features)

    # 创建环境
    env = TradingEnvironment(prices=prices, features=features)
    state = env.reset()
    state_size = len(state)
    action_size = 3

    # 创建 Agent
    agent = DQNAgent(state_size, action_size)
    trainer = RLTrainer()

    # 开始训练
    history = trainer.train(env, agent, episodes=30)
    for row in history:
        print(row)
    print("\n训练完成")

    # 评价
    print("最终资产:", history[-1]["portfolio"])


if __name__ == "__main__":
    main()
