"""V1.6 机器学习交易引擎测试"""
import numpy as np
import pandas as pd
import pytest

from ml.feature_engineering import FeatureEngineering
from ml.trainer import ModelTrainer
from ml.xgboost_model import XGBoostPredictor

from dataset.loader import DatasetLoader

from models.registry import ModelRegistry

from prediction.ensemble import EnsemblePredictor

from intraday.ml_trader import MLTrader

try:
    import torch  # noqa: F401

    torch_ok = True
    _torch_err = None
except Exception as e:  # ImportError / OSError(DLL) 均跳过 PyTorch 测试
    torch_ok = False
    _torch_err = str(e)

if torch_ok:
    from ml.lstm_model import LSTMModel  # noqa: E402
    from ml.transformer_model import MarketTransformer  # noqa: E402


class TestFeatureEngineering:
    def test_features(self):
        df = pd.DataFrame(
            {
                "close": [10, 10.5, 10.2, 10.8, 11.0, 11.2, 11.5, 10.9, 11.3, 12.0, 12.1, 11.8, 12.3, 12.5, 12.2, 12.8, 13.0, 13.2, 12.9, 13.5, 13.8, 14.0, 14.2, 14.1, 14.5],
                "volume": [1000] * 25,
            }
        )
        out = FeatureEngineering().create_features(df)
        assert "return" in out.columns
        assert "ma5" in out.columns
        assert "ma20" in out.columns
        assert "volatility" in out.columns
        assert "volume_ratio" in out.columns
        assert "target" in out.columns
        assert out["target"].isin([0, 1]).all()


class TestXGBoost:
    def test_predict(self):
        rng = np.random.default_rng(7)
        X = rng.normal(size=(100, 5))
        y = (X[:, 0] > 0).astype(int)
        model = XGBoostPredictor()
        model.train(X, y)
        prob = model.predict(X[:3])
        assert prob.shape == (3,)
        assert ((prob >= 0) & (prob <= 1)).all()


class TestDatasetLoader:
    def test_split(self, tmp_path):
        p = tmp_path / "data.csv"
        pd.DataFrame({"close": range(20)}).to_csv(p, index=False)
        loader = DatasetLoader()
        df = loader.load_csv(str(p))
        assert len(df) == 20
        train, test = loader.split(df)
        assert len(train) == 16
        assert len(test) == 4


class TestTrainer:
    def test_evaluate(self):
        pred = np.array([1, 0, 1])
        real = np.array([1, 0, 1])
        assert ModelTrainer().evaluate(pred, real)["accuracy"] == 1.0


class TestModelRegistry:
    def test_best(self):
        reg = ModelRegistry()
        reg.register("xgb", object(), 0.8)
        reg.register("lstm", object(), 0.9)
        assert reg.best()["score"] == 0.9


class TestEnsemble:
    def test_buy(self):
        out = EnsemblePredictor().predict(xgb=0.82, lstm=0.75, transformer=0.80)
        assert out["signal"] == "BUY"
        assert round(out["score"], 3) == 0.795

    def test_sell(self):
        out = EnsemblePredictor().predict(xgb=0.1, lstm=0.2, transformer=0.3)
        assert out["signal"] == "SELL"

    def test_hold(self):
        out = EnsemblePredictor().predict(xgb=0.5, lstm=0.5, transformer=0.5)
        assert out["signal"] == "HOLD"


class TestMLTrader:
    def test_open(self):
        out = MLTrader().decide({"signal": "BUY", "score": 0.796})
        assert out["action"] == "OPEN_POSITION"
        assert out["confidence"] == 0.796

    def test_close(self):
        assert MLTrader().decide({"signal": "SELL", "score": 0.2})["action"] == "CLOSE_POSITION"

    def test_wait(self):
        assert MLTrader().decide({"signal": "HOLD", "score": 0.5})["action"] == "WAIT"


class TestTorchModels:
    def test_requires_torch(self):
        if not torch_ok:
            pytest.skip(f"torch 不可用（{_torch_err}），跳过 PyTorch 模型测试")

    def test_lstm(self):
        self.test_requires_torch()
        model = LSTMModel(input_size=4)
        x = torch.randn(8, 10, 4)
        out = model(x)
        assert out.shape == (8, 1)

    def test_transformer(self):
        self.test_requires_torch()
        model = MarketTransformer(feature_size=8)
        x = torch.randn(10, 8)
        out = model(x)
        assert out.shape == (1,)
