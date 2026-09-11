"""V1.9 因子自动挖掘系统：搜索因子组合。"""

import itertools


class FactorMiner:
    """对候选因子做组合搜索（2~3 个因子组合）。"""

    def search(self, factors: list) -> list[tuple]:
        """枚举 2~3 元因子组合。

        Args:
            factors: 候选因子列表。

        Returns:
            组合列表。
        """
        combinations: list[tuple] = []
        for size in range(2, 4):
            for combo in itertools.combinations(factors, size):
                combinations.append(combo)
        return combinations
