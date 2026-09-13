"""V3.0.6 主程序：策略生命周期 + 自动进化。

运行：python main_v306.py
"""
from __future__ import annotations

from evolution.evolution_controller import (
    EvolutionController,
)
from evolution.genetic_algorithm import (
    GeneticAlgorithmV281 as GeneticAlgorithm,
)
from evolution.strategy_generator import (
    StrategyGeneratorV281 as StrategyGenerator,
)
from strategy_lab.strategy_health import (
    StrategyHealth,
)


def main():
    print("=" * 70)
    print("AI HEDGE FUND OS V3.0.6")
    print("Strategy Lifecycle Engine")
    print("=" * 70)

    generator = StrategyGenerator()
    genetic = GeneticAlgorithm()
    controller = EvolutionController(
        generator,
        genetic,
    )
    population = generator.generate_population(100)

    # 模拟已有回测结果
    for i, strategy in enumerate(population):
        strategy.metrics = {
            "sharpe": 1.5 - (i / 100),
            "max_drawdown": -0.10 - (i / 500),
            "win_rate": 0.50,
            "total_return": 0.20 - (i / 500),
        }

    health_engine = StrategyHealth()
    retired = 0
    healthy = 0
    watch = 0
    for strategy in population:
        health = health_engine.evaluate(strategy.metrics)
        strategy.status = health["status"]
        if strategy.status == "RETIRED":
            retired += 1
        elif strategy.status == "HEALTHY":
            healthy += 1
        else:
            watch += 1
    print("\nHEALTHY:", healthy)
    print("WATCH:", watch)
    print("RETIRED:", retired)

    # 自动进化
    population = controller.evolve(
        population,
        population_size=100,
    )
    print("\nNew Population:", len(population))
    print("\nV3.0.6 COMPLETE")


if __name__ == "__main__":
    main()
