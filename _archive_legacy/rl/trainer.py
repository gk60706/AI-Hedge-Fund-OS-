"""V1.7 RL 训练器（研究/模拟）。"""


class RLTrainer:
    """强化学习训练器。"""

    def train(self, env, agent, episodes=50):
        history = []
        for episode in range(episodes):
            state = env.reset()
            total_reward = 0
            done = False
            while not done:
                action = agent.act(state)
                next_state, reward, done, info = env.step(action)
                total_reward += reward
                state = next_state
                agent.decay_epsilon()
            history.append(
                {
                    "episode": episode + 1,
                    "reward": total_reward,
                    "epsilon": agent.epsilon,
                    "portfolio": info["portfolio_value"],
                }
            )
        return history
