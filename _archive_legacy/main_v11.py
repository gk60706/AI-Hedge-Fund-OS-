"""AI Hedge Fund OS V1.1 启动入口（自主投资 Agent 升级版）。

LangGraph 工作流：Research → Quant → Risk → Decision。
仅研究与模拟，禁止自动实盘交易。
"""
from agent_core.graph import app

state = {
    "stock": {"code": "300394"},
    "market": {"trend": "BULL"},
    "research": [],
    "risk": {},
    "strategy": {},
    "decision": "",
    "memory": [],
}

result = app.invoke(state)
print(result)
