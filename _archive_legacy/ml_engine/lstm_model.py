"""V2.7 LSTM 时间序列模型：学习股票价格走势。"""
import torch
import torch.nn as nn


class LSTMModel(nn.Module):
    """LSTM 序列预测。"""

    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(input_size=5, hidden_size=64, batch_first=True)
        self.fc = nn.Linear(64, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])
