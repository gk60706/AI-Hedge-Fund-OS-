"""V2.7 机器学习 Alpha 预测引擎（Machine Learning Alpha Engine）单元测试。"""

import numpy as np
import pytest

from ml_engine.feature_engineering import FeatureEngineering
from ml_engine.trainer import ModelTrainer
from alpha.factor_library import FactorLibrary
from alpha.alpha_generator import AlphaGenerator
from model.model_manager import ModelManager


class TestFeatureEngineering:
    def test_create_features(self):
        stock = {"pe": 20, "roe": 0.15, "return_20": 0.05, "volume_ratio": 1.2, "fund_flow": 5000}
        out = FeatureEngineering().create_features(stock)
        assert out["pe"] == 20
        assert out["roe"] == 0.15
        assert out["momentum"] == 0.05
        assert out["volume_factor"] == 1.2
        assert out["capital_flow"] == 5000


class TestFactorLibrary:
    def test_calculate(self):
        data = {"pe": 10, "return_20": 0.08, "roe": 0.2, "fund_flow": 100}
        out = FactorLibrary().calculate(data)
        assert out["value"] == pytest.approx(0.1)
        assert out["momentum"] == 0.08
        assert out["quality"] == 0.2
        assert out["capital"] == 100


class TestAlphaGenerator:
    def test_generate(self):
        # 0.85*0.4 + 0.75*0.3 + 0.9*0.3 = 0.34 + 0.225 + 0.27 = 0.835
        assert AlphaGenerator().generate(0.85, 0.75, 0.9) == 0.835


class TestModelManager:
    def test_add_get(self):
        mm = ModelManager()
        mm.add("xgb", object())
        assert mm.get("xgb") is not None
        assert mm.get("none") is None


class TestModelTrainer:
    def test_train_pipeline(self, capsys):
        class FakeModel:
            def train(self, X, y):
                pass

        ModelTrainer().train_pipeline(FakeModel(), np.array([1]), np.array([2]))
        out = capsys.readouterr().out
        assert "开始训练模型" in out
        assert "训练完成" in out


class TestXGBoostAlpha:
    def test_train_predict(self):
        from ml_engine.xgboost_model import XGBoostAlpha

        X = np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0], [4.0, 5.0]])
        y = np.array([1.0, 2.0, 3.0, 4.0])
        model = XGBoostAlpha()
        model.train(X, y)
        out = model.predict(np.array([[5.0, 6.0]]))
        assert len(out) == 1
        assert np.isfinite(out[0])


class TestLSTMModel:
    def test_forward_shape(self):
        import torch
        from ml_engine.lstm_model import LSTMModel

        model = LSTMModel()
        x = torch.randn(2, 10, 5)
        out = model(x)
        assert out.shape == (2, 1)


class TestMarketTransformer:
    def test_forward_shape(self):
        import torch
        from ml_engine.transformer_model import MarketTransformer

        model = MarketTransformer()
        x = torch.randn(2, 8, 64)
        out = model(x)
        assert out.shape == (2, 8, 64)
