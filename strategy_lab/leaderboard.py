"""V2.8/V2.8.1 策略排行榜。

V2.8 版：StrategyLeaderboard（add + rank，保存最强策略）
V2.8.1 版：StrategyLeaderboardV281（rank + top，直接对策略列表排序）
"""


class StrategyLeaderboard:
    """V2.8 框架演示版：保存并排序策略。"""

    def __init__(self):
        self.strategies = []

    def add(self, strategy, score):
        self.strategies.append({
            "strategy": strategy,
            "score": score,
        })

    def rank(self):
        return sorted(self.strategies, key=lambda x: x["score"], reverse=True)


class StrategyLeaderboardV281:
    """V2.8.1 可运行版：按策略指标 score 排序。"""

    def rank(self, strategies):
        return sorted(
            strategies,
            key=lambda s: s.metrics.get("score", -999),
            reverse=True,
        )

    def top(self, strategies, n=10):
        return self.rank(strategies)[:n]
