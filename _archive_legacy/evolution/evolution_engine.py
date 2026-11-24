"""V1.9 策略进化引擎：创建种群 → 评价 → 选择 → 变异 → 下一代。"""


class EvolutionEngine:
    """串联生成器与优化器完成一代策略进化。"""

    def __init__(self, generator, optimizer):
        self.generator = generator
        self.optimizer = optimizer

    def create_population(self, size: int) -> list:
        """创建第一代策略种群。"""
        return [self.generator.generate() for _ in range(size)]

    def evolve(self, strategies: list, scores: list) -> list:
        """选择精英并变异产生下一代。

        Args:
            strategies: 当前代策略。
            scores: 对应得分。

        Returns:
            下一代策略列表。
        """
        best = self.optimizer.select(strategies, scores)
        new = []
        for strategy in best:
            new.append(self.optimizer.mutate(strategy))
        return new
