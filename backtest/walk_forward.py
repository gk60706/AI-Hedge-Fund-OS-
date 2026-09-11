"""V1.8 回测系统：Walk Forward 切分。"""


class WalkForward:
    """Walk Forward 样本切分（训练/测试）。"""

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
