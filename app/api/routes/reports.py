"""研究报告检索 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.reports.service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("")
def list_reports() -> dict:
    """列出全部已生成的研究报告。"""
    reports = ReportService().list_reports()
    return {"total": len(reports), "reports": reports}


@router.get("/{report_id}")
def get_report(report_id: str) -> dict:
    """按 report_id 读取研究报告内容。"""
    content = ReportService().get_report(report_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
    return {"report_id": report_id, "content": content}
