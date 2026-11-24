"""回测系统：Walk Forward 切分。

V1.8 WalkForward（简单比例切分） + V3.5 WalkForwardEngine（滚动前推窗口）。
"""

from __future__ import annotations


class WalkForward:
    """V1.8 Walk Forward 样本切分（训练/测试）。"""

    def split(self, data, train_ratio: float = 0.7):
        """按比例切分训练与测试集。

        Args:
            data: 序列化数据（列表 / numpy 数组 / DataFrame）。
            train_ratio: 训练集占比。

        Returns:
            (train, test)
        """
        size = int(len(data) * train_ratio)
        train = data[:size]
        test = data[size:]
        return train, test


class WalkForwardEngine:
    """V3.5 滚动前推窗口（Train → Test，逐步前移）。"""

    def __init__(self, train_size: int, test_size: int):
        self.train_size = train_size
        self.test_size = test_size

    def generate_windows(self, data):
        n = len(data)
        start = 0
        windows = []
        while start + self.train_size + self.test_size <= n:
            train_start = start
            train_end = start + self.train_size
            test_end = train_end + self.test_size
            windows.append(
                {
                    "train": data.iloc[train_start:train_end],
                    "test": data.iloc[train_end:test_end],
                }
            )
            start += self.test_size
        return windows
