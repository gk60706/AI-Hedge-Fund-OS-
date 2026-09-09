"""V1.7 强化学习交易 Agent：环境 / 状态 / 动作 / 奖励 / DQN / PPO / 训练器。

Windows 兼容说明：本机存在 torch 的 DLL 依赖链加载问题
（WinError 126/1114，c10.dll/shm.dll 初始化失败）。先加载
xgboost 可稳定解锁 torch 的 DLL 依赖，故在包入口统一处理，
保证 rl.dqn_agent / rl.ppo_agent 可正常 import。
"""

try:
    import xgboost  # noqa: F401
except Exception:
    pass
