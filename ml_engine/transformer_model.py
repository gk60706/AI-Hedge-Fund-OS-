"""V2.7 Transformer 行情模型接口：金融版 GPT 升级方向。"""
import torch.nn as nn


class MarketTransformer(nn.Module):
    """Transformer 行情编码器。"""

    def __init__(self):
        super().__init__()
        self.encoder_layer = (
            nn.TransformerEncoderLayer(d_model=64, nhead=8)
        )
        self.encoder = (
            nn.TransformerEncoder(self.encoder_layer, num_layers=3)
        )

    def forward(self, x):
        return self.encoder(x)
