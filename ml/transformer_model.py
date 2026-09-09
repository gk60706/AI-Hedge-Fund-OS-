"""V1.6 Transformer 行情理解模型。"""

import torch
import torch.nn as nn


class MarketTransformer(nn.Module):
    """Transformer 编码器行情模型。"""

    def __init__(self, feature_size: int):
        super().__init__()
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=feature_size,
            nhead=4,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=3)
        self.output = nn.Linear(feature_size, 1)

    def forward(self, x):
        x = self.encoder(x)
        return self.output(x[-1])
