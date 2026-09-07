"""LangGraph 图节点实现。

节点职责：
1. fetch_market_data_node —— 通过 AkShare 获取行情与公司信息；
2. generate_report_node —— 通过 OpenAI Responses API 生成研究报告。
"""
from __future__ import annotations

from app.ai.client import OpenAIClient
from app.ai.prompts import (
    RESEARCH_SYSTEM_PROMPT,
    build_market_summary,
    build_research_prompt,
)
from app.ai.state import ResearchState
from app.market.provider import MarketDataProvider


def fetch_market_data_node(state: ResearchState) -> dict:
    """节点 1：获取行情与公司信息。数据获取失败不阻断图流程。"""
    provider = MarketDataProvider()
    symbol = state["symbol"]
    try:
        df = provider.get_daily_history(symbol, state.get("start_date"), state.get("end_date"))
        bars = provider.to_history_response(symbol, df)
        market_rows = [bar.model_dump(mode="json") for bar in bars]
        company_info = provider.get_individual_info(symbol)
    except Exception as exc:  # noqa: BLE001 —— 数据失败交给下游生成节点说明
        market_rows = []
        company_info = {}
        state["error"] = str(exc)
    return {"market_rows": market_rows, "company_info": company_info, "error": state.get("error")}


def generate_report_node(state: ResearchState) -> dict:
    """节点 2：调用 OpenAI Responses API 生成研究报告。"""
    client = OpenAIClient()
    prompt = build_research_prompt(
        symbol=state["symbol"],
        focus=state.get("focus", ""),
        market_summary=build_market_summary(state.get("market_rows", [])),
        company_info=str(state.get("company_info", {})),
    )
    report = client.complete(prompt=prompt, system=RESEARCH_SYSTEM_PROMPT)
    if state.get("error"):
        report = f"> 注意：行情数据获取失败（{state['error']}），以下内容仅基于公司信息。\n\n{report}"
    return {"report": report}
