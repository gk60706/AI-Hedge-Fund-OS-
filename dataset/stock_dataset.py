"""V1.8 股票数据集管理。"""

import pandas as pd


class StockDataset:
    """管理多只股票的数据集，支持合并为带 code 列的宽表。"""

    def __init__(self, data: dict[str, pd.DataFrame]):
        """Args:
            data: {code: DataFrame} 行情字典。
        """
        self.data = data

    def merge(self) -> pd.DataFrame:
        """合并全部股票为一张表，追加 code 列。

        Returns:
            拼接后的 DataFrame。
        """
        frames = []
        for code, df in self.data.items():
            df = df.copy()
            df["code"] = code
            frames.append(df)
        return pd.concat(frames)
