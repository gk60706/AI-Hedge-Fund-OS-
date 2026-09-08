"""V1.1 Agent 状态管理：LangGraph 共享状态定义。"""
from typing import TypedDict


class FundState(TypedDict):
    stock: dict
    market: dict
    research: list
    risk: dict
    strategy: dict
    decision: str
    memory: list
