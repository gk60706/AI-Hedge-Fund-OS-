"""V2.8.1 可运行的 AI Strategy Evolution Engine（AI策略自动进化实验室）。

闭环：生成 100 策略 → 回测 → 评价 → 淘汰/保留 → 交叉 → 变异 → 下一代，共 20 代。
最终输出 Champion Strategy（仅研究用途，禁止自动实盘）。
"""
import numpy as np

from evolution.strategy_generator import StrategyGeneratorV281 as StrategyGenerator
from evolution.genetic_algorithm import GeneticAlgorithmV281 as GeneticAlgorithm
from strategy_lab.signal_engine import StrategySignalEngine
from strategy_lab.evaluator import StrategyEvaluatorV281 as StrategyEvaluator
from strategy_lab.leaderboard import StrategyLeaderboardV281 as StrategyLeaderboard
from strategy_lab.lifecycle import StrategyLifecycleV281 as StrategyLifecycle
from backtest.engine import BacktestEngineV281 as BacktestEngine


def create_demo_data(n=1500):
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0003, 0.015, n)
    prices = 100 * np.cumprod(1 + returns)
    features = {
        "momentum": rng.random(n),
        "value": rng.random(n),
        "capital": rng.random(n),
        "volume": rng.random(n),
    }
    return prices, features


def main():
    prices, features = create_demo_data()
    generator = StrategyGenerator()
    signal_engine = StrategySignalEngine()
    backtester = BacktestEngine()
    evaluator = StrategyEvaluator()
    leaderboard = StrategyLeaderboard()
    lifecycle = StrategyLifecycle()
    genetic = GeneticAlgorithm()
    population = generator.generate_population(100)
    generations = 20

    for generation in range(generations):
        print(f"\nGeneration {generation + 1}")
        for strategy in population:
            signals = signal_engine.generate(strategy, features)
            equity = backtester.run(prices, signals)
            metrics = evaluator.evaluate(equity)
            strategy.metrics = metrics
            strategy.status = lifecycle.evaluate(strategy)
        ranked = leaderboard.rank(population)
        champion = ranked[0]
        print("Champion Score:", round(champion.metrics["score"], 4))
        print("Return:", round(champion.metrics["total_return"] * 100, 2), "%")
        print("Sharpe:", round(champion.metrics["sharpe"], 2))
        print("Max DD:", round(champion.metrics["max_drawdown"] * 100, 2), "%")
        population = genetic.evolve(population, 100)

    final_rank = leaderboard.rank(population)
    print("\n===== FINAL CHAMPION =====")
    champion = final_rank[0]
    print(champion.dna.to_dict())
    print(champion.metrics)


if __name__ == "__main__":
    main()
