"""V2.8/V2.8.1 遗传算法策略进化。

V2.8 版：GeneticAlgorithm（简单复制+变异）
V2.8.1 版：GeneticAlgorithmV281（Selection → Crossover → Mutation 完整闭环）
"""
import random
import copy


class GeneticAlgorithm:
    """V2.8 框架演示版：保留前 10 个，各变异 5 次产生下一代。"""

    def evolve(self, strategies):
        survivors = strategies[:10]
        new = []
        for s in survivors:
            for i in range(5):
                child = s.mutate()
                new.append(child)
        return new


class GeneticAlgorithmV281:
    """V2.8.1 可运行版：选择精英 + 交叉 + 变异。"""

    def select(self, population, elite_size=10):
        population.sort(key=lambda s: s.metrics.get("score", -999), reverse=True)
        return population[:elite_size]

    def crossover(self, parent_a, parent_b):
        child = copy.deepcopy(parent_a)
        a = parent_a.dna
        b = parent_b.dna
        genes = [
            "momentum_weight", "value_weight", "capital_weight",
            "volume_weight", "buy_threshold", "stop_loss",
            "take_profit", "holding_period", "max_position",
        ]
        for gene in genes:
            if random.random() < 0.5:
                value = getattr(b, gene)
                setattr(child.dna, gene, value)
        child.metrics = {}
        return child

    def evolve(self, population, population_size=100):
        elites = self.select(population)
        new_population = [copy.deepcopy(s) for s in elites]
        while len(new_population) < population_size:
            parent_a = random.choice(elites)
            parent_b = random.choice(elites)
            child = self.crossover(parent_a, parent_b)
            if random.random() < 0.3:
                child.mutate()
            new_population.append(child)
        return new_population
