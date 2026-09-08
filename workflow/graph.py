"""LangGraph 交易工作流 (V0.9)

market → research → decision 三段式 Agent 工作流。
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph


class State(TypedDict):
    """LangGraph 状态（LangGraph 1.x 使用 TypedDict）。"""

    market: dict
    research: dict
    decision: str


def market_node(state: State) -> dict:
    state["market"] = {"score": 80}
    return state


def research_node(state: State) -> dict:
    state["research"] = {"score": 85}
    return state


def decision_node(state: State) -> dict:
    state["decision"] = "BUY"
    return state


workflow = StateGraph(State)
workflow.add_node("market", market_node)
workflow.add_node("research", research_node)
workflow.add_node("decision", decision_node)
workflow.set_entry_point("market")
workflow.add_edge("market", "research")
workflow.add_edge("research", "decision")
workflow.add_edge("decision", END)
app = workflow.compile()
