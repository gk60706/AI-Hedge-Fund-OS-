"""V1.6 LSTM 时间序列价格预测模型。"""

import torch
import torch.nn as nn


class LSTMModel(nn.Module):
    """LSTM 价格预测网络。"""

    def __init__(self, input_size: int):
        super().__init__()
        self.lstm = nn.LSTM(input_size, 64, batch_first=True)
        self.fc = nn.Linear(64, 1)

    def forward(self, x):
        output, _ = self.lstm(x)
        result = self.fc(output[:, -1, :])
        return result
