from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.cio_agent import generate_cio_report
from tools.market_tool import get_a_share_quote

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
