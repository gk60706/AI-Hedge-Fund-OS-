from __future__ import annotations

import copy
import random

from evolution.alpha_crossover import AlphaCrossover
from evolution.alpha_mutation import AlphaMutation


class AlphaEvolution:
    def __init__(self):
        self.crossover = AlphaCrossover()
        self.mutation = AlphaMutation()

    def evolve(self, ranked, population_size=100):
        if not ranked:
            return []
        elite_count = max(5, population_size // 10)
        elites = ranked[:elite_count]
        new_population = [
            copy.deepcopy(item["expression"])
            for item in elites
        ]
        while len(new_population) < population_size:
            parent_a = random.choice(elites)["expression"]
            parent_b = random.choice(elites)["expression"]
            child = self.crossover.crossover(
                parent_a,
                parent_b,
            )
            child = self.mutation.mutate(
                child,
                probability=0.30,
            )
            new_population.append(child)
        return new_population
