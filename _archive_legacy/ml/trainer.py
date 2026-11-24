"""V1.6 模型训练管理器：训练与评价。"""


class ModelTrainer:
    """模型训练管理器。"""

    def evaluate(self, prediction, real) -> dict:
        accuracy = (prediction == real).mean()
        return {"accuracy": accuracy}
