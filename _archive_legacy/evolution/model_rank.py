"""V1.8 AI 策略排行榜：按 Sharpe 排序多策略。"""


class ModelRank:
    """策略排行榜（按评价分数降序）。"""

    def __init__(self):
        self.models: list[dict] = []

    def add(self, name: str, result: dict) -> None:
        """登记一个策略的评价结果。

        Args:
            name: 策略名。
            result: Performance.analyze 输出，含 sharpe 字段。
        """
        self.models.append({
            "name": name,
            "score": result["sharpe"],
        })

    def ranking(self) -> list[dict]:
        """按分数降序返回排行榜。"""
        return sorted(self.models, key=lambda x: x["score"], reverse=True)
