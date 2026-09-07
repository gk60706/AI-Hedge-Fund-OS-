"""AI 研究 API：驱动 LangGraph 研究流程并落盘报告。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai.graph import build_research_graph
from app.reports.service import ReportService

router = APIRouter(prefix="/api/v1/research", tags=["research"])


class ResearchRequest(BaseModel):
    """研究请求体。"""

    symbol: str = Field(..., description="股票代码")
    focus: str = Field("综合", description="研究重点，如：业绩、估值、行业、技术面")
    start_date: str | None = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: str | None = Field(None, description="结束日期 YYYY-MM-DD")


class ResearchResponse(BaseModel):
    """研究响应。"""

    symbol: str
    report_id: str
    report: str


@router.post("/analyze", response_model=ResearchResponse)
def analyze(req: ResearchRequest) -> ResearchResponse:
    try:
        graph = build_research_graph()
        result = graph.invoke(
            {
                "symbol": req.symbol,
                "focus": req.focus,
                "start_date": req.start_date,
                "end_date": req.end_date,
            }
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"研究流程执行失败: {exc}") from exc

    report = result.get("report", "")
    report_id = ReportService().save(
        symbol=req.symbol,
        content=report,
        meta={"focus": req.focus, "model": "openai-responses-api"},
    )
    return ResearchResponse(symbol=req.symbol, report_id=report_id, report=report)
