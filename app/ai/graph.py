"""LangGraph 研究报告生成图。

流程图：START -> fetch_market_data -> generate_report -> END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.ai.nodes import fetch_market_data_node, generate_report_node
from app.ai.state import ResearchState


def build_research_graph():
    """构建并编译研究流程图。"""
    builder = StateGraph(ResearchState)
    builder.add_node("fetch_market_data", fetch_market_data_node)
    builder.add_node("generate_report", generate_report_node)
    builder.add_edge(START, "fetch_market_data")
    builder.add_edge("fetch_market_data", "generate_report")
    builder.add_edge("generate_report", END)
    return builder.compile()
