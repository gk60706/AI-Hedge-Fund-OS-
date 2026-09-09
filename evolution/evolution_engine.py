"""V1.2 策略进化引擎：淘汰低分策略并对幸存策略进行变异。"""


class EvolutionEngine:
    """策略进化引擎。

    - ``evolve``：按分数淘汰（score >= 80 存活）
    - ``mutate``：对策略参数进行变异（仓位放大 1.1 倍）
    """

    SURVIVE_SCORE = 80

    def evolve(self, strategies: list) -> list:
        """筛选出达到存活分数线的策略。"""
        survivors = []
        for s in strategies:
            if s["score"] >= self.SURVIVE_SCORE:
                survivors.append(s)
        return survivors

    def mutate(self, strategy: dict) -> dict:
        """对策略做一次简单变异（调整仓位），返回新策略 dict。"""
        strategy = dict(strategy)
        strategy["position"] = strategy.get("position", 0.2) * 1.1
        return strategy
