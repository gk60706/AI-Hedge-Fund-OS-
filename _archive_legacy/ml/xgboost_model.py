"""V1.6 XGBoost 涨跌预测模型。"""

from xgboost import XGBClassifier


class XGBoostPredictor:
    """XGBoost 分类器：预测次日上涨概率。"""

    def __init__(self):
        self.model = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
        )

    def train(self, X, y) -> None:
        self.model.fit(X, y)

    def predict(self, X):
        probability = self.model.predict_proba(X)
        return probability[:, 1]
