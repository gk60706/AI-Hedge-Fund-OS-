from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.cio_agent import generate_cio_report
from agents.decision_agent import decision_agent
from agents.quant_agent import quant_agent
from agents.research_agent import research_agent
from agents.risk_agent import risk_agent
from tools.market_tool import get_a_share_quote, get_history, get_stock_price

REPORT_DIR = Path("reports")


class ResearchState(TypedDict, total=False):
    code: str
    market_data: dict[str, Any]
    report: str
    report_path: str
    error: str


def market_node(state: ResearchState) -> ResearchState:
    state["market_data"] = get_a_share_quote(state["code"])
    return state


def cio_node(state: ResearchState) -> ResearchState:
    state["report"] = generate_cio_report(state["market_data"])
    return state


def save_report_node(state: ResearchState) -> ResearchState:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    code = state["code"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"{code}_{timestamp}.md"
    content = (
        "# AI Hedge Fund OS 股票研究报告\n\n"
        f"- 股票代码：{code}\n"
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}\n\n"
        "## 行情快照\n\n"
        f"```json\n{state['market_data']}\n```\n\n"
        f"## CIO 分析\n\n{state['report']}\n"
    )
    path.write_text(content, encoding="utf-8")
    state["report_path"] = str(path)
    return state


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("market", market_node)
    graph.add_node("cio", cio_node)
    graph.add_node("save_report", save_report_node)
    graph.add_edge(START, "market")
    graph.add_edge("market", "cio")
    graph.add_edge("cio", "save_report")
    graph.add_edge("save_report", END)
    return graph.compile()


research_graph = build_graph()


def run_research(code: str) -> dict[str, Any]:
    normalized = code.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        normalized = normalized.removeprefix(prefix)
    if not normalized.isdigit() or len(normalized) != 6:
        raise ValueError("股票代码必须是 6 位数字，例如 300394")
    return research_graph.invoke({"code": normalized})


# ---------------------------------------------------------------- V0.2 多 Agent 工作流
# 图结构：market（行情）→ agents（Research/Quant/Risk）→ decision（综合决策）
# 使用 TypedDict 定义 State 以兼容 LangGraph 1.x（ChatGPT V0.2 原稿为 class State(dict)）。

class AgentResearchState(TypedDict, total=False):
    code: str
    stock: dict[str, Any]
    history: Any
    results: list[Any]
    decision: Any


def v2_market_node(state: AgentResearchState) -> AgentResearchState:
    state["stock"] = get_stock_price(state["code"])
    state["history"] = get_history(state["code"])
    return state


def v2_agent_node(state: AgentResearchState) -> AgentResearchState:
    results = [
        research_agent(state["stock"]),
        quant_agent(state["history"]),
        risk_agent(state["stock"]),
    ]
    state["results"] = results
    return state


def v2_decision_node(state: AgentResearchState) -> AgentResearchState:
    state["decision"] = decision_agent(state["stock"], state["results"])
    return state


def build_agent_graph():
    graph = StateGraph(AgentResearchState)
    graph.add_node("market", v2_market_node)
    graph.add_node("agents", v2_agent_node)
    graph.add_node("decision", v2_decision_node)
    graph.add_edge(START, "market")
    graph.add_edge("market", "agents")
    graph.add_edge("agents", "decision")
    graph.add_edge("decision", END)
    return graph.compile()


agent_research_graph = build_agent_graph()


def run_agent_research(code: str) -> dict[str, Any]:
    """V0.2 多 Agent 研究：返回 {stock, results, decision}."""
    normalized = code.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        normalized = normalized.removeprefix(prefix)
    if not normalized.isdigit() or len(normalized) != 6:
        raise ValueError("股票代码必须是 6 位数字，例如 300394")
    return agent_research_graph.invoke({"code": normalized})
