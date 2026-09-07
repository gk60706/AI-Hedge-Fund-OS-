"""AI Hedge Fund OS 入口。

当前版本仅提供三大能力：行情获取 / AI 研究 / 研究报告。
安全边界：禁止自动实盘交易，本应用不含任何下单、撤单、账户或持仓接口。
"""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import market, reports, research
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例（便于测试复用）。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI Hedge Fund OS — 行情获取 + AI 研究 + 研究报告（禁止自动实盘交易）",
    )

    app.include_router(market.router)
    app.include_router(research.router)
    app.include_router(reports.router)

    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    return app


app = create_app()
