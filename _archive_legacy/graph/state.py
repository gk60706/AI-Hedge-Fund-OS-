"""V2.0 多智能体 AI 基金经理系统：LangGraph 共享状态。

所有 Agent 共享同一个 FundState（TypedDict）。
"""

from typing import TypedDict


class FundState(TypedDict):
    """AI 基金委员会共享状态。"""

    stock_code: str
    research_report: str
    quant_signal: str
    trader_signal: str
    risk_result: str
    macro_view: str
    final_decision: str
    confidence: float
