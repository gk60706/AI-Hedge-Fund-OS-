"""V2.7 XGBoost Alpha 预测模型：预测未来 5 日收益。"""
from xgboost import XGBRegressor


class XGBoostAlpha:
    """XGBoost 收益预测。"""

    def __init__(self):
        self.model = XGBRegressor(n_estimators=200, max_depth=5)

    def train(self, X, y):
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)
