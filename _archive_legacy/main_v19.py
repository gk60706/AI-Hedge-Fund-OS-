"""AI Hedge Fund OS V1.9 主程序：AI 策略自动进化演示。

生成第一代策略 → 模拟回测评分 → 进化产生下一代。
研究/模拟用途，不连接任何实盘交易接口。
"""

from evolution.strategy_generator import StrategyGenerator
from evolution.evolution_engine import EvolutionEngine
from evolution.genetic_optimizer import GeneticOptimizer

generator = StrategyGenerator()
optimizer = GeneticOptimizer()
engine = EvolutionEngine(generator, optimizer)

# 第一代策略
population = engine.create_population(100)
print("第一代策略数量:", len(population))

# 模拟回测结果
scores = [i % 100 for i in range(100)]
population = engine.evolve(population, scores)
print("进化后策略:", len(population))
