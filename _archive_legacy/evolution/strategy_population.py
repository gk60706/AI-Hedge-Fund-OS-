"""V1.9 策略种群系统：管理一代策略集合。"""


class StrategyPopulation:
    """策略种群容器。"""

    def __init__(self):
        self.population: list = []

    def add(self, strategy) -> None:
        """加入一个策略。"""
        self.population.append(strategy)

    def size(self) -> int:
        """当前种群规模。"""
        return len(self.population)
