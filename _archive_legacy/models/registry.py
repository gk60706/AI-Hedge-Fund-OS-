"""V1.6 AI 模型仓库：按得分自动选出最优模型。"""


class ModelRegistry:
    """模型仓库。"""

    def __init__(self):
        self.models = {}

    def register(self, name: str, model, score: float) -> None:
        self.models[name] = {"model": model, "score": score}

    def best(self):
        return max(self.models.values(), key=lambda x: x["score"])
