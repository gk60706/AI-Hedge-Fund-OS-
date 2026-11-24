"""V1.6 数据特征工程系统：收益率 / 均线 / 波动率 / 量比 / 标签。"""

import numpy as np
import pandas as pd


class FeatureEngineering:
    """特征工程：从行情 DataFrame 构造 ML 特征与标签。"""

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        data = df.copy()
        # 收益率
        data["return"] = data["close"] / data["close"].shift(1) - 1
        # 均线
        data["ma5"] = data["close"].rolling(5).mean()
        data["ma20"] = data["close"].rolling(20).mean()
        # 波动率
        data["volatility"] = data["return"].rolling(20).std()
        # 成交量变化
        data["volume_ratio"] = data["volume"] / data["volume"].rolling(20).mean()
        # 标签：次日收盘是否上涨
        data["target"] = (data["close"].shift(-1) > data["close"]).astype(int)
        return data.dropna()
