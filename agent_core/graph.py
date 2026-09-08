"""V1.1 LangGraph 核心流程：Research → Quant → Risk → Decision。"""
from langgraph.graph import StateGraph

from agent_core.state import FundState


def research_node(state):
    state["research"].append(
        {
            "agent": "Research",
            "score": 85,
        }
    )
    return state


def quant_node(state):
    state["research"].append(
        {
            "agent": "Quant",
            "score": 90,
        }
    )
    return state


def risk_node(state):
    state["risk"] = {"risk": "LOW"}
    return state


def decision_node(state):
    scores = [x["score"] for x in state["research"]]
    avg = sum(scores) / len(scores)
    if avg > 80:
        state["decision"] = "BUY"
    else:
        state["decision"] = "WAIT"
    return state


graph = StateGraph(FundState)
graph.add_node("research", research_node)
graph.add_node("quant", quant_node)
graph.add_node("risk", risk_node)
graph.add_node("decision", decision_node)
graph.set_entry_point("research")
graph.add_edge("research", "quant")
graph.add_edge("quant", "risk")
graph.add_edge("risk", "decision")
app = graph.compile()
