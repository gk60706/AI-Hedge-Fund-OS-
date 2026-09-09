"""V1.7 PPO Agent 基础版：Actor-Critic 网络框架。"""

import torch
import torch.nn as nn


class ActorCritic(nn.Module):
    """Actor-Critic 网络。"""

    def __init__(self, state_size, action_size):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(state_size, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
        )
        self.actor = nn.Linear(128, action_size)
        self.critic = nn.Linear(128, 1)

    def forward(self, x):
        hidden = self.shared(x)
        logits = self.actor(hidden)
        value = self.critic(hidden)
        return logits, value
