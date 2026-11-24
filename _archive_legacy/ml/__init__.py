"""V1.6 机器学习交易引擎：特征工程 / 预测模型 / 模型仓库。

Windows 兼容说明：本机存在 torch 的 DLL 依赖链加载问题
（WinError 126/1114，c10.dll/shm.dll 初始化失败）。先加载
xgboost 可稳定解锁 torch 的 DLL 依赖，故在包入口统一处理，
保证 ml.lstm_model / ml.transformer_model 可正常 import。
"""

try:
    import xgboost  # noqa: F401
except Exception:
    pass
