"""分钟 K 线生成 (V0.8)

将 tick 流聚合成 DataFrame 序列。
"""
import pandas as pd


class KlineEngine:
    """分钟 K 线引擎。"""

    def __init__(self):
        self.data = {}

    def add_tick(self, tick: dict) -> None:
        """加入一个 tick 到对应股票的 K 线序列。"""
        code = tick["code"]
        row = {"price": tick["price"], "volume": tick["volume"]}
        if code not in self.data:
            self.data[code] = []
        self.data[code].append(row)

    def get_dataframe(self, code: str) -> pd.DataFrame:
        """返回某只股票的 K 线 DataFrame。"""
        return pd.DataFrame(self.data.get(code, []))
