"""V3.0.6 自动策略淘汰 + 新策略生成（接回 V2.8 Genetic Algorithm）。"""
from __future__ import annotations

import random


class EvolutionController:
    def __init__(
        self,
        generator,
        genetic_algorithm,
    ):
        self.generator = generator
        self.genetic = genetic_algorithm

    def evolve(
        self,
        population,
        population_size: int = 100,
    ):
        alive = [
            strategy
            for strategy in population
            if strategy.status != "RETIRED"
        ]
        # 如果剩余策略太少，自动补充随机策略
        if len(alive) < 10:
            while len(alive) < 20:
                alive.append(
                    self.generator.generate()
                )
        return self.genetic.evolve(
            alive,
            population_size=population_size,
        )
