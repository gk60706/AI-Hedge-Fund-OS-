"""V3.9.1 alpha evolution: rank -> elites + mutate/crossover offspring."""
from __future__ import annotations

import numpy as np

from evolution.crossover import crossover
from evolution.mutation import mutate


def evolve(
    expressions,
    scores,
    population_size: int = 100,
    elite_ratio: float = 0.10,
    seed: int = 42,
):
    """按分数排名保留精英，其余通过交叉 + 变异补足。"""
    rng = np.random.default_rng(seed)
    if not expressions:
        return []
    ranked = sorted(
        zip(expressions, scores),
        key=lambda item: item[1],
        reverse=True,
    )
    n_elite = max(1, int(population_size * elite_ratio))
    elites = [expr for expr, _ in ranked[:n_elite]]
    offspring = []
    while len(elites) + len(offspring) < population_size:
        a = rng.choice(ranked, replace=True)[0]
        b = rng.choice(ranked, replace=True)[0]
        child = crossover(a, b, rng)
        child = mutate(child, rng, 0.15)
        offspring.append(child)
    return (elites + offspring)[:population_size]
