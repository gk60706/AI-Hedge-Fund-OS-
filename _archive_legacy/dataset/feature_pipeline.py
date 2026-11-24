"""V1.8 AI 因子流水线。

基于原始行情生成 AI 训练因子：日收益、均线、量比、动量。
"""

import pandas as pd


class FeaturePipeline:
    """行情因子工程。"""

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成因子列并去除含缺失值的行。

        Args:
            df: 含 close / volume 列的原始行情。

        Returns:
            含 return_1 / ma5 / ma20 / volume_change / momentum 的 DataFrame。
        """
        data = df.copy()
        data["return_1"] = data.close / data.close.shift(1) - 1
        data["ma5"] = data.close.rolling(5).mean()
        data["ma20"] = data.close.rolling(20).mean()
        data["volume_change"] = data.volume / data.volume.rolling(20).mean()
        data["momentum"] = data.close / data.close.shift(20) - 1
        return data.dropna()
