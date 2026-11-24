"""V2.8 自动策略发现与进化系统主流程（框架演示：100 策略 → 评价 → 排行）。"""

from evolution.strategy_generator import StrategyGeneratorV28 as StrategyGenerator
from strategy_lab.evaluator import StrategyEvaluator
from strategy_lab.leaderboard import StrategyLeaderboard

generator = StrategyGenerator()
evaluator = StrategyEvaluator()
board = StrategyLeaderboard()

for i in range(100):
    genes = generator.generate()
    result = evaluator.evaluate(genes)
    board.add(genes, result["score"])

ranking = board.rank()
print("TOP策略")
print(ranking[:5])
