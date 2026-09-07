"""LangGraph 图状态定义。"""
from __future__ import annotations

from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    """研究流程各节点之间传递的状态。"""

    symbol: str
    start_date: str | None
    end_date: str | None
    focus: str
    market_rows: list[dict[str, Any]]
    company_info: dict[str, Any]
    report: str
    error: str | None
