"""V1.2 总进化流程：AI 发现因子 → 生成策略（研究用途，无实盘交易）。"""

from evolution.alpha_agent import AlphaAgent
from evolution.evolution_engine import EvolutionEngine
from evolution.strategy_agent import StrategyAgent


def main() -> None:
    alpha = AlphaAgent()
    strategy_agent = StrategyAgent()
    engine = EvolutionEngine()

    factor = alpha.discover(None)
    strategy = strategy_agent.create(factor)
    # 对单一策略做一次存活判定（研究演示）
    survivors = engine.evolve([{"name": strategy["name"], "score": 85, "code": ""}])

    print("发现因子:", factor)
    print("生成策略:", strategy)
    print("存活策略:", survivors)


if __name__ == "__main__":
    main()
