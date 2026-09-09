"""V1.6 数据集加载系统。"""

import pandas as pd


class DatasetLoader:
    """数据集加载器。"""

    def load_csv(self, path: str) -> pd.DataFrame:
        df = pd.read_csv(path)
        return df

    def split(self, df: pd.DataFrame):
        size = int(len(df) * 0.8)
        return df[:size], df[size:]
