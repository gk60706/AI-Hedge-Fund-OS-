"""V1.9 遗传算法优化器：选择 / 交叉 / 变异。"""

import random
from dataclasses import replace

from strategy.strategy_template import StrategyDNA


class GeneticOptimizer:
    """模拟自然选择：保留精英、交叉繁殖、随机变异。"""

    def select(self, population: list, scores: list) -> list:
        """按得分降序选出前 10 名精英策略。

        Args:
            population: 策略列表。
            scores: 与 population 一一对应的得分列表。

        Returns:
            精英策略列表。
        """
        ranked = sorted(
            zip(population, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return [item[0] for item in ranked[:10]]

    def crossover(self, parent1: StrategyDNA, parent2: StrategyDNA) -> StrategyDNA:
        """交叉：子代继承父本，ma_fast 取双亲均值。"""
        child = replace(parent1, ma_fast=(parent1.ma_fast + parent2.ma_fast) // 2)
        return child

    def mutate(self, strategy: StrategyDNA) -> StrategyDNA:
        """变异：调用 DNA 的 mutation。"""
        return strategy.mutation()
