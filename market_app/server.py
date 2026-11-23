from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analytics, data_sources as ds, signal_ledger
from .config import (
    APP_NAME,
    APP_NAME_EN,
    DATA_DIR,
    STATIC_DIR,
    VERSION,
    WATCHLIST_FILE,
)

app = FastAPI(title=f"{APP_NAME} API", version=VERSION)

_default_watchlist = ["600519.SH", "300750.SZ", "000001.SZ", "601318.SH", "510300.SH"]
_watchlist_lock = threading.RLock()

_screen_jobs: dict[str, dict[str, Any]] = {}
_screen_lock = threading.RLock()
_screen_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="screener")


# ---------------------------------------------------------------------------
# Watchlist persistence
# ---------------------------------------------------------------------------

def _read_watchlist() -> list[str]:
    with _watchlist_lock:
        if not WATCHLIST_FILE.is_file():
            return list(_default_watchlist)
        try:
            payload = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
            symbols = payload.get("symbols", [])
            normalized = []
            for symbol in symbols:
                try:
                    normalized.append(ds.normalize_symbol(symbol))
                except ValueError:
                    continue
            return normalized[:40]
        except Exception:
            return list(_default_watchlist)


def _write_watchlist(symbols: list[str]) -> None:
    with _watchlist_lock:
        temp = WATCHLIST_FILE.with_suffix(".tmp")
        temp.write_text(
            json.dumps({"symbols": symbols[:40]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(WATCHLIST_FILE)


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="UI not found")
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "name": APP_NAME,
        "version": VERSION,
        "time": ds.now_text(),
        "data_dir": str(DATA_DIR),
        "mode": "local",
    }


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------

@app.get("/api/search")
def search(q: str = Query(default=""), limit: int = Query(default=12, ge=1, le=30)):
    if not q.strip():
        return {"items": [], "error": "请输入代码或名称"}
    try:
        return {"items": ds.search_stocks(q, limit=limit)}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@app.get("/api/resolve")
def resolve(symbol: str = Query(default="")):
    return ds.resolve_symbol(symbol)


@app.get("/api/quote")
def quote(symbols: str = Query(default="")):
    requested = [item.strip() for item in symbols.split(",") if item.strip()][:50]
    if not requested:
        return {"items": []}
    try:
        return {"items": ds.get_quotes(requested), "fetched_at": ds.now_text()}
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@app.get("/api/indices")
def indices():
    symbols = ["000001.SH", "399001.SZ", "399006.SZ", "000688.SH"]
    try:
        items = ds.get_quotes(symbols)
        sources = sorted({item.get("source", "") for item in items if item.get("source")})
        return {
            "items": items,
            "fetched_at": ds.now_text(),
            "source": " / ".join(sources) or "行情源不可用",
        }
    except Exception as exc:
        return {"items": [], "error": str(exc)}


@app.get("/api/analyze")
def analyze(
    symbol: str = Query(default=""),
    period: str = Query(default="day"),
    bars: int = Query(default=320, ge=120, le=640),
):
    if not symbol.strip():
        raise HTTPException(status_code=400, detail="请提供股票代码")
    try:
        result = analytics.analyze_symbol(symbol, period=period, bars=bars)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "分析失败"))
    return result


@app.get("/api/minute")
def minute(symbol: str = Query(default=""), period: str = Query(default="m5"), count: int = Query(default=240, ge=80, le=480)):
    try:
        frame, provenance = ds.get_tencent_minute(symbol, period=period, count=count)
        return {
            "ok": True,
            "symbol": ds.normalize_symbol(symbol),
            "series": frame.tail(count).to_dict(orient="records"),
            "provenance": provenance,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/api/watchlist")
def get_watchlist():
    symbols = _read_watchlist()
    items: list[dict[str, Any]] = []
    if symbols:
        try:
            items = ds.get_quotes(symbols)
        except Exception:
            items = []
    return {
        "symbols": symbols,
        "items": items,
        "fetched_at": ds.now_text(),
        "source": "腾讯财经 qt.gtimg.cn",
    }


class WatchlistInput(BaseModel):
    symbol: str = Field(min_length=1)
    action: str = Field(default="add", pattern="^(add|remove)$")


@app.post("/api/watchlist")
def update_watchlist(payload: WatchlistInput):
    symbols = _read_watchlist()
    if payload.action == "add":
        resolved = ds.resolve_symbol(payload.symbol)
        if not resolved.get("ok"):
            raise HTTPException(status_code=404, detail=resolved.get("error", "未找到标的"))
        symbol = resolved["symbol"]
        if symbol not in symbols:
            if len(symbols) >= 40:
                raise HTTPException(status_code=400, detail="自选最多 40 只")
            symbols.append(symbol)
    else:
        try:
            symbol = ds.normalize_symbol(payload.symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        symbols = [item for item in symbols if item != symbol]

    _write_watchlist(symbols)
    return {"ok": True, "symbols": symbols}


@app.get("/api/universes")
def universes():
    options = [
        {"id": "hs300", "name": "沪深300", "note": "大盘蓝筹，300 只", "count": None},
        {"id": "zz500", "name": "中证500", "note": "中盘成长，500 只", "count": None},
        {"id": "broad", "name": "宽基池", "note": "沪深300 + 中证500，约 800 只", "count": None},
        {"id": "watchlist", "name": "我的自选", "note": "自选列表内的标的", "count": len(_read_watchlist())},
        {"id": "custom", "name": "自定义代码", "note": "最多 50 只，逗号分隔", "count": None},
    ]
    for option in options:
        if option["id"] in ("hs300", "zz500", "broad"):
            try:
                option["count"] = len(ds.get_universe(option["id"]))
            except Exception:
                option["count"] = None
    return {"items": options, "fetched_at": ds.now_text()}


# ---------------------------------------------------------------------------
# Screener jobs
# ---------------------------------------------------------------------------

class ScreenRequest(BaseModel):
    universe: str = Field(default="hs300")
    symbols: list[str] = []
    conditions: list[str] = []
    match_mode: str = Field(default="at_least", pattern="^(all|any|at_least)$")
    min_matches: int = Field(default=2, ge=1, le=8)
    max_results: int = Field(default=80, ge=1, le=200)
    quality_filter: bool = True
    strict_gates: bool = False
    daily_top_k: int = Field(default=5, ge=0, le=20)
    cooldown_days: int = Field(default=10, ge=1, le=60)


def _build_screen_symbols(request: ScreenRequest) -> list[dict[str, Any]]:
    if request.universe == "custom":
        items: list[dict[str, Any]] = []
        for raw in request.symbols[:50]:
            resolved = ds.resolve_symbol(raw)
            if resolved.get("ok"):
                items.append({
                    "symbol": resolved["symbol"],
                    "name": resolved.get("name", resolved["symbol"]),
                })
        return items

    if request.universe == "watchlist":
        return [{"symbol": symbol, "name": symbol} for symbol in _read_watchlist()]

    return ds.get_universe(request.universe)


def _run_screen(job_id: str, request: ScreenRequest) -> None:
    try:
        symbols = _build_screen_symbols(request)
        if not symbols:
            raise ValueError("股票池为空")
        with _screen_lock:
            if job_id in _screen_jobs:
                _screen_jobs[job_id]["status"] = "running"
                _screen_jobs[job_id]["total"] = len(symbols)

        def progress(done: int, total: int, current: str) -> None:
            with _screen_lock:
                job = _screen_jobs.get(job_id)
                if job:
                    job["done"] = done
                    job["progress"] = round(done / max(total, 1) * 100, 1)
                    job["current"] = current

        result = analytics.screen_universe(
            symbols,
            conditions=request.conditions,
            match_mode=request.match_mode,
            min_matches=request.min_matches,
            max_results=request.max_results,
            quality_filter=request.quality_filter,
            daily_top_k=request.daily_top_k,
            cooldown_days=request.cooldown_days,
            strict_gates=request.strict_gates,
            progress=progress,
        )
        try:
            result["ledger_inserted"] = signal_ledger.record_top_picks(
                result, universe=request.universe
            )
        except Exception as exc:
            result["ledger_inserted"] = 0
            result["ledger_error"] = str(exc)[:160]
        with _screen_lock:
            job = _screen_jobs.get(job_id)
            if job:
                job["status"] = "completed"
                job["progress"] = 100.0
                job["result"] = result
                job["finished_at"] = ds.now_text()
    except Exception as exc:
        with _screen_lock:
            job = _screen_jobs.get(job_id)
            if job:
                job["status"] = "failed"
                job["error"] = str(exc)
                job["finished_at"] = ds.now_text()


@app.post("/api/screen")
def create_screen(request: ScreenRequest):
    job_id = uuid.uuid4().hex[:12]
    with _screen_lock:
        _screen_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "done": 0,
            "total": 0,
            "current": "",
            "result": None,
            "error": None,
            "created_at": ds.now_text(),
        }
    _screen_executor.submit(_run_screen, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/screen/{job_id}")
def get_screen(job_id: str):
    with _screen_lock:
        job = _screen_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return dict(job)


@app.get("/api/ledger")
def ledger(days: int = Query(default=30, ge=1, le=3650), limit: int = Query(default=200, ge=1, le=2000)):
    return signal_ledger.recent(days=days, limit=limit)


@app.get("/api/sources")
def sources(refresh: bool = Query(default=False)):
    return {"items": ds.get_source_status(refresh=refresh), "fetched_at": ds.now_text()}


@app.get("/api/source-check")
def source_check(symbol: str = Query(default="600519.SH")):
    result = analytics.analyze_symbol(symbol, "day", 160)
    return {
        "ok": result.get("ok"),
        "symbol": result.get("symbol"),
        "provenance": result.get("provenance"),
        "checks": result.get("source_checks"),
    }

