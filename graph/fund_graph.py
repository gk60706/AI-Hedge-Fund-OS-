"""V2.0 多智能体基金协作图（LangGraph 工作流）。"""

from langgraph.graph import StateGraph


def build_graph():
    """构建 AI 基金委员会工作流：research → quant → risk → cio。

    Returns:
        编译后的 LangGraph 图。
    """
    graph = StateGraph(dict)
    graph.add_node("research", lambda x: x)
    graph.add_node("quant", lambda x: x)
    graph.add_node("risk", lambda x: x)
    graph.add_node("cio", lambda x: x)
    graph.set_entry_point("research")
    graph.add_edge("research", "quant")
    graph.add_edge("quant", "risk")
    graph.add_edge("risk", "cio")
    return graph.compile()
