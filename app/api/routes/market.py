"""行情获取 API（只读，无任何交易能力）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.market.provider import MarketDataProvider
from app.market.schemas import HistoryResponse, QuoteResponse

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/history", response_model=HistoryResponse)
def get_history(
    symbol: str = Query(..., description="股票代码，如 000001 或 1"),
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    adjust: str = Query("qfq", description="复权方式: qfq / hfq / ''"),
) -> HistoryResponse:
    provider = MarketDataProvider()
    try:
        normalized = provider.normalize_symbol(symbol)
        df = provider.get_daily_history(normalized, start_date, end_date, adjust=adjust)
        bars = provider.to_history_response(normalized, df, adjust=adjust)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"行情获取失败: {exc}") from exc
    return HistoryResponse(symbol=normalized, adjust=adjust, total=len(bars), bars=bars)


@router.get("/quote", response_model=QuoteResponse)
def get_quote(symbol: str = Query(..., description="股票代码")) -> QuoteResponse:
    provider = MarketDataProvider()
    try:
        normalized = provider.normalize_symbol(symbol)
        raw = provider.get_spot_quote(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"行情获取失败: {exc}") from exc
    return QuoteResponse(
        symbol=normalized,
        name=raw.get("名称"),
        price=_safe_float(raw.get("最新价")),
        change_pct=_safe_float(raw.get("涨跌幅")),
        volume=_safe_float(raw.get("成交量")),
        amount=_safe_float(raw.get("成交额")),
        raw=raw,
    )


def _safe_float(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
