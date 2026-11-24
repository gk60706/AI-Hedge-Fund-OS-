"""V1.3 策略排名系统：按分数排序并选出冠军策略。"""


class StrategyRanking:
    """策略排名系统。"""

    def rank(self, results: list) -> list:
        """按 score 从高到低排序。"""
        ranking = sorted(results, key=lambda x: x["score"], reverse=True)
        return ranking

    def top_strategy(self, results: list) -> dict:
        """返回排名第一的策略。"""
        ranking = self.rank(results)
        return ranking[0]
