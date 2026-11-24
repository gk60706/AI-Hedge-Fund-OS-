"""V2.7 自动训练管理器。"""


class ModelTrainer:
    """自动训练流程。"""

    def train_pipeline(self, model, X, y):
        print("开始训练模型")
        model.train(X, y)
        print("训练完成")
