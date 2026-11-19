from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


# ============================================================
# Paths
# ============================================================

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    UI_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / "desktop"
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    UI_ROOT = Path(__file__).resolve().parent

UI_FILE = UI_ROOT / "ui.html"

REPORTS_DIR = PROJECT_ROOT / "reports"
RESEARCH_DIR = PROJECT_ROOT / "research"

PROVIDERS_FILE = PROJECT_ROOT / "configs" / "ai_providers.yaml"
ENV_FILE = PROJECT_ROOT / ".env"

_PROVIDERS_HEADER = (
    "# AI Hedge Fund OS V3.10 自定义大模型配置（OpenAI 兼容协议）\n"
    "# 该文件可由桌面端「Provider 管理」面板自动生成；\n"
    "# API Key 写入 .env，变量名为 AIH_<ID>_API_KEY。\n"
)

app = FastAPI(title="AI Hedge Fund OS Desktop API")


# ============================================================
# Logging
# ============================================================

logger = logging.getLogger("ai_hedge_fund_desktop")
logger.setLevel(logging.INFO)
logger.propagate = False

_log_lock = threading.Lock()
_log_lines: list[str] = []


class MemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            with _log_lock:
                _log_lines.append(message)
                if len(_log_lines) > 200:
                    del _log_lines[:-200]
        except Exception:
            self.handleError(record)


if not any(isinstance(h, MemoryLogHandler) for h in logger.handlers):
    _handler = MemoryLogHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(_handler)


# ============================================================
# Research jobs
# ============================================================

jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_research_executor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="research",
)


class ResearchRequest(BaseModel):
    symbol: str = Field(min_length=1)
    as_of_date: str | None = None
    call_budget: int = 30
    allow_missing_agents: bool = True


# ============================================================
# Tencent market data cache
# ============================================================

_HTTP_TIMEOUT = 8
_CACHE_TTL = 10.0
_cache_lock = threading.Lock()
_http_cache: dict[str, tuple[float, str]] = {}

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _http_get(url: str) -> str:
    now = time.monotonic()

    with _cache_lock:
        cached = _http_cache.get(url)
        if cached is not None:
            cached_at, cached_text = cached
            if now - cached_at < _CACHE_TTL:
                return cached_text

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _BROWSER_UA,
            "Referer": "https://gu.qq.com/",
            "Accept": "*/*",
            "Connection": "close",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=_HTTP_TIMEOUT,
    ) as response:
        raw = response.read()

    content = raw.decode("gbk", errors="replace")

    with _cache_lock:
        _http_cache[url] = (time.monotonic(), content)

        if len(_http_cache) > 256:
            expired = [
                key
                for key, (cached_at, _) in _http_cache.items()
                if time.monotonic() - cached_at >= _CACHE_TTL
            ]
            for key in expired:
                _http_cache.pop(key, None)

    return content


# ============================================================
# Stock symbol helpers
# ============================================================

def _normalize_market(market: str, code: str) -> str | None:
    market = market.lower()
    code = code.strip()

    if not code.isdigit():
        return None

    if market in ("sh", "sz", "bj"):
        return market

    return None


def _symbol_from_market(market: str, code: str) -> str:
    suffix = {
        "sh": "SH",
        "sz": "SZ",
        "bj": "BJ",
    }[market]

    return f"{code}.{suffix}"


def _market_from_symbol(symbol: str) -> tuple[str, str] | None:
    value = symbol.strip().upper()

    match = re.fullmatch(r"(\d{6})\.(SH|SZ|BJ)", value)

    if match:
        code, suffix = match.groups()
        market = {
            "SH": "sh",
            "SZ": "sz",
            "BJ": "bj",
        }[suffix]
        return market, code

    if re.fullmatch(r"\d{6}", value):
        if value.startswith(("6", "9")):
            return "sh", value

        if value.startswith(("0", "3")):
            return "sz", value

        if value.startswith(("4", "8")):
            return "bj", value

    return None


def _parse_smartbox(text: str, limit: int = 10) -> list[dict[str, str]]:
    match = re.search(
        r'v_hint\s*=\s*"([^"]*)"',
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return []

    raw_items = match.group(1).split("^")
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for raw_item in raw_items:
        fields = raw_item.split("~")

        if len(fields) < 5:
            continue

        market = _normalize_market(fields[0], fields[1])
        code = fields[1].strip()
        name = fields[2].strip()
        stock_type = fields[4].strip()

        if market is None or not name:
            continue

        symbol = _symbol_from_market(market, code)

        if symbol in seen:
            continue

        seen.add(symbol)

        results.append(
            {
                "market": market,
                "code": code,
                "symbol": symbol,
                "name": name,
                "type": stock_type,
            }
        )

        if len(results) >= limit:
            break

    return results


def _search_stocks(query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip()

    if not query:
        return []

    limit = max(1, min(int(limit), 50))

    encoded = urllib.parse.urlencode({"q": query, "t": "all"})
    url = f"https://smartbox.gtimg.cn/s3/?{encoded}"

    response = _http_get(url)
    results = _parse_smartbox(response, limit)

    # Tencent smartbox normally handles both code and Chinese-name
    # matching. Keep the local filtering as a defensive fallback.
    if not results:
        return []

    return results


# ============================================================
# Tencent quote helpers
# ============================================================

def _to_float(value: Any) -> float | None:
    try:
        text = str(value).strip()

        if not text:
            return None

        result = float(text)

        if result != result or result in (float("inf"), float("-inf")):
            return None

        return result
    except (TypeError, ValueError, OverflowError):
        return None


def _quote_from_fields(
    symbol: str,
    fields: list[str],
) -> dict[str, Any] | None:
    if len(fields) <= 45:
        return None

    name = fields[1].strip()

    if not name:
        return None

    market_info = _market_from_symbol(symbol)

    if market_info is None:
        return None

    market, code = market_info

    # Tencent quote field indexes.
    price = _to_float(fields[3])
    prev_close = _to_float(fields[4])
    open_price = _to_float(fields[5])

    if price is None:
        return None

    volume = _to_float(fields[6])
    quote_time = fields[30].strip()

    change = _to_float(fields[31])
    change_pct = _to_float(fields[32])
    high = _to_float(fields[33])
    low = _to_float(fields[34])

    amount_wan = _to_float(fields[37])
    turnover = _to_float(fields[38])
    pe_ttm = _to_float(fields[39])

    market_cap = _to_float(fields[44])

    if market_cap is None:
        market_cap = _to_float(fields[45])

    return {
        "symbol": _symbol_from_market(market, code),
        "code": code,
        "name": name,
        "price": price,
        "prev_close": prev_close,
        "open": open_price,
        "high": high,
        "low": low,
        "change": change,
        "change_pct": change_pct,
        "volume": volume,
        "amount": amount_wan * 10000 if amount_wan is not None else None,
        "turnover": turnover,
        "pe_ttm": pe_ttm,
        "market_cap": market_cap,
        "time": quote_time or None,
    }


def _fetch_quotes(symbols: list[str]) -> list[dict[str, Any]]:
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()

    for raw_symbol in symbols:
        info = _market_from_symbol(raw_symbol)

        if info is None:
            continue

        market, code = info
        symbol = _symbol_from_market(market, code)

        if symbol in seen:
            continue

        seen.add(symbol)
        normalized.append((market, code))

    if not normalized:
        return []

    normalized = normalized[:50]

    query = ",".join(
        f"{market}{code}"
        for market, code in normalized
    )

    url = f"https://qt.gtimg.cn/q={query}"

    try:
        response = _http_get(url)
    except Exception:
        logger.warning("腾讯行情接口请求失败", exc_info=True)
        return []

    results: list[dict[str, Any]] = []

    for market, code in normalized:
        symbol = _symbol_from_market(market, code)

        pattern = re.compile(
            rf'v_{re.escape(market + code)}\s*=\s*"([^"]*)"',
        )

        match = pattern.search(response)

        if not match:
            continue

        try:
            fields = match.group(1).split("~")
            item = _quote_from_fields(symbol, fields)

            if item is not None:
                results.append(item)

        except Exception:
            logger.warning(
                "行情解析失败: %s",
                symbol,
                exc_info=True,
            )

    return results


# ============================================================
# Stock resolution
# ============================================================

def _resolve_stock(value: str) -> dict[str, Any]:
    raw_value = value.strip()
    value = raw_value
    suffix = ""

    if "." in value:
        core, _, tail = value.partition(".")
        value = core.strip()
        suffix = tail.strip().upper()

    not_found = {
        "ok": False,
        "error": f"未找到该股票代码：{raw_value}",
    }

    if not value:
        return not_found

    try:
        items = _search_stocks(value, limit=20)
    except Exception:
        logger.warning(
            "股票联想查询失败: %s",
            value,
            exc_info=True,
        )
        return not_found

    candidates = []

    for item in items:
        try:
            name = str(item.get("name", "")).strip()

            if "\\u" in name:
                name = json.loads('"' + name + '"')

            stock_type = str(item.get("type", "")).strip().upper()
            market = str(item.get("market", "")).strip().lower()
            code = str(item.get("code", "")).strip()

            if not stock_type.startswith("GP"):
                continue

            if market not in ("sh", "sz", "bj"):
                continue

            if not re.fullmatch(r"\d{6}", code):
                continue

            if not name:
                continue

            if suffix and _symbol_from_market(market, code).split(".")[-1] != suffix:
                continue

            candidates.append({
                "code": code,
                "name": name,
                "symbol": _symbol_from_market(market, code),
            })

        except (ValueError, TypeError, KeyError):
            continue

    # 纯数字：必须代码完全匹配
    if re.fullmatch(r"\d{5,6}", value):
        for item in candidates:
            if item["code"] == value:
                return {
                    "ok": True,
                    "symbol": item["symbol"],
                    "name": item["name"],
                }

        return not_found

    # 名称完全匹配
    for item in candidates:
        if item["name"] == value:
            return {
                "ok": True,
                "symbol": item["symbol"],
                "name": item["name"],
            }

    # 名称前缀匹配
    for item in candidates:
        if item["name"].startswith(value):
            return {
                "ok": True,
                "symbol": item["symbol"],
                "name": item["name"],
            }

    # 名称包含匹配
    if len(value) >= 2:
        for item in candidates:
            if value in item["name"]:
                return {
                    "ok": True,
                    "symbol": item["symbol"],
                    "name": item["name"],
                }

    return not_found


# ============================================================

def _expand_env_default(text: str) -> str:
    """把 ${VAR:-默认值} 形式展开为默认值或环境变量值。"""
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2) or ""
        return os.environ.get(name, default)

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-([^}]*))?\}", repl, str(text))


def _load_env_into_process() -> None:
    """把项目 .env 读进进程环境，之后新建的 registry 才能拿到 key。"""
    try:
        from ai_team.adapters import load_env_file

        for name, value in load_env_file(ENV_FILE).items():
            if value:
                os.environ.setdefault(name, value)

    except Exception:
        logger.warning("读取 .env 失败: %s", ENV_FILE, exc_info=True)


def _read_provider_entries() -> list[dict[str, Any]]:
    if not PROVIDERS_FILE.is_file():
        return []

    try:
        data = yaml.safe_load(
            PROVIDERS_FILE.read_text(encoding="utf-8")
        ) or {}

    except Exception:
        logger.warning(
            "读取 Provider 配置失败: %s",
            PROVIDERS_FILE,
            exc_info=True,
        )
        return []

    items = data.get("providers") if isinstance(data, dict) else None

    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


def _save_provider_entries(entries: list[dict[str, Any]]) -> None:
    PROVIDERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if PROVIDERS_FILE.is_file():
        backup = PROVIDERS_FILE.with_suffix(".yaml.bak")
        try:
            backup.write_text(
                PROVIDERS_FILE.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("备份 Provider 配置失败", exc_info=True)

    body = yaml.safe_dump(
        {"providers": entries},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )

    tmp = PROVIDERS_FILE.with_suffix(".yaml.tmp")
    tmp.write_text(_PROVIDERS_HEADER + body, encoding="utf-8")
    tmp.replace(PROVIDERS_FILE)


def _set_env_value(name: str, value: str) -> None:
    """写入 .env（保留其它项），同时更新当前进程环境。"""
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    if ENV_FILE.is_file():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    replaced = False
    output: list[str] = []

    for line in lines:
        if line.strip().startswith(f"{name}="):
            output.append(f"{name}={value}")
            replaced = True
        else:
            output.append(line)

    if not replaced:
        output.append(f"{name}={value}")

    ENV_FILE.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.environ[name] = value


def _provider_key_env(entry: dict[str, Any]) -> str:
    provider_id = str(entry.get("provider_id") or "").strip().upper()
    explicit = str(entry.get("api_key_env") or "").strip()
    return explicit or f"AIH_{provider_id}_API_KEY"


def _get_provider_rows() -> list[dict[str, Any]]:
    from ai_team.providers import build_custom_registry

    _load_env_into_process()

    entries = _read_provider_entries()

    if not entries:
        return []

    available: list[str] = []
    skipped: dict[str, str] = {}

    if PROVIDERS_FILE.is_file():
        try:
            description = build_custom_registry(
                PROVIDERS_FILE,
                timeout=10,
            ).describe()
            available = description.get("available") or []
            skipped = description.get("skipped") or {}

        except Exception:
            logger.warning("Provider 状态探测失败", exc_info=True)

    rows: list[dict[str, Any]] = []

    for entry in entries:
        provider_id = str(entry.get("provider_id") or "").strip()

        if not provider_id:
            continue

        enabled = bool(entry.get("enabled", True))
        key_env = _provider_key_env(entry)
        has_key = bool(os.environ.get(key_env, "").strip())

        if not enabled:
            status = "disabled"
        elif not has_key:
            status = "missing_key"
        elif provider_id in available:
            status = "ready"
        elif skipped.get(provider_id):
            status = "error"
        else:
            status = "unknown"

        rows.append(
            {
                "provider_id": provider_id,
                "display_name": str(entry.get("display_name") or provider_id),
                "base_url": _expand_env_default(entry.get("base_url") or ""),
                "model": _expand_env_default(entry.get("model") or ""),
                "protocol": str(entry.get("protocol") or "openai"),
                "api_key_env": key_env,
                "has_key": has_key,
                "enabled": enabled,
                "status": status,
                "tags": entry.get("tags") or [],
            }
        )

    return rows


# ============================================================
# Research execution
# ============================================================

def _run_research(job_id: str, payload: dict[str, Any]) -> None:
    try:
        from ai_team.research_pipeline import V310ResearchPipeline

        from ai_team.providers import (
            build_custom_registry,
        )

        symbol = payload["symbol"]
        as_of_date = payload.get("as_of_date")
        call_budget = payload.get("call_budget", 30)
        allow_missing_agents = payload.get(
            "allow_missing_agents",
            True,
        )

        _load_env_into_process()

        with _jobs_lock:
            jobs[job_id]["status"] = "running"
            jobs[job_id]["started_at"] = time.time()

        logger.info("研究任务启动: %s", job_id)
        logger.info("标的: %s", symbol)
        logger.info("调用预算: %s", call_budget)

        config_candidates = [
            PROJECT_ROOT / "configs" / "ai_providers.yaml",
            PROJECT_ROOT / "configs" / "ai_providers.yml",
            PROJECT_ROOT / "config" / "providers.yaml",
            PROJECT_ROOT / "config" / "providers.yml",
        ]

        config_path = next(
            (
                path
                for path in config_candidates
                if path.is_file()
            ),
            None,
        )

        registry = (
            build_custom_registry(
                config_path,
                timeout=180,
            )
            if config_path is not None
            else None
        )

        pipeline = V310ResearchPipeline(project_root=PROJECT_ROOT)

        participants: list[str] = []

        if registry is not None:
            try:
                available = list(registry.describe().get("available") or [])
            except Exception:
                available = []

            # 管线只认识 chatgpt / grok / hark 三个席位（含提示词角色）
            participants = [
                seat for seat in ("chatgpt", "grok", "hark") if seat in available
            ]

        if not participants:
            raise RuntimeError(
                "没有可用的研究席位：请在「Provider 管理」面板为 chatgpt / grok / hark 配置 API Key 并启用"
            )

        logger.info("参与研究的 Provider: %s", ", ".join(participants))

        result = pipeline.run_live(
            symbol=symbol,
            registry=registry,
            as_of_date=as_of_date or date.today().isoformat(),
            reports_dir=REPORTS_DIR,
            participants=participants,
            allow_missing_agents=allow_missing_agents,
            call_budget=call_budget,
        )

        with _jobs_lock:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["result"] = result
            jobs[job_id]["finished_at"] = time.time()

        logger.info("研究任务完成: %s", job_id)

    except Exception as exc:
        error = str(exc)

        logger.error(
            "研究任务失败: %s\n%s",
            error,
            traceback.format_exc(),
        )

        with _jobs_lock:
            if job_id in jobs:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = error
                jobs[job_id]["finished_at"] = time.time()


# ============================================================
# Existing endpoints
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    if not UI_FILE.is_file():
        raise HTTPException(
            status_code=404,
            detail="Desktop UI not found",
        )

    try:
        return HTMLResponse(
            UI_FILE.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
    }


@app.get("/api/providers")
async def providers():
    try:
        return _get_provider_rows()
    except Exception as exc:
        logger.error(
            "Provider 加载失败: %s",
            exc,
            exc_info=True,
        )
        return []


_PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


class ProviderInput(BaseModel):
    provider_id: str = ""
    display_name: str = ""
    base_url: str = ""
    model: str = ""
    api_key: str | None = None
    api_key_env: str | None = None
    tags: list[str] = []
    enabled: bool = True
    timeout: float | None = None
    max_tokens: int | None = None
    temperature: float | None = None


def _provider_presets() -> list[dict[str, Any]]:
    return [
        {"provider_id": "openai", "display_name": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "tags": ["global"]},
        {"provider_id": "deepseek", "display_name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "tags": ["cn", "reasoning"]},
        {"provider_id": "moonshot", "display_name": "Kimi (Moonshot)", "base_url": "https://api.moonshot.cn/v1", "model": "kimi-k2-turbo-preview", "tags": ["cn", "long-context"]},
        {"provider_id": "dashscope", "display_name": "Qwen (DashScope)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "tags": ["cn"]},
        {"provider_id": "zhipu", "display_name": "Zhipu GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4.5", "tags": ["cn"]},
        {"provider_id": "minimax", "display_name": "MiniMax", "base_url": "https://api.minimaxi.com/v1", "model": "MiniMax-M2", "tags": ["cn"]},
        {"provider_id": "siliconflow", "display_name": "SiliconFlow", "base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-ai/DeepSeek-V3", "tags": ["cn", "aggregator"]},
        {"provider_id": "openrouter", "display_name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini", "tags": ["global", "aggregator"]},
        {"provider_id": "groq", "display_name": "Groq", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "tags": ["global", "fast"]},
        {"provider_id": "xai", "display_name": "Grok (xAI)", "base_url": "https://api.x.ai/v1", "model": "grok-4", "tags": ["global"]},
        {"provider_id": "gemini", "display_name": "Gemini (OpenAI 兼容)", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.0-flash", "tags": ["global"]},
        {"provider_id": "ollama", "display_name": "Ollama 本地模型", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b", "tags": ["local"]},
    ]


def _build_provider_entry(payload: ProviderInput, provider_id: str) -> dict[str, Any]:
    base_url = payload.base_url.strip()
    model = payload.model.strip()

    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="base_url 必须以 http:// 或 https:// 开头")

    if not model:
        raise HTTPException(status_code=400, detail="model 不能为空")

    key_env = (payload.api_key_env or "").strip() or f"AIH_{provider_id.upper()}_API_KEY"

    entry: dict[str, Any] = {
        "provider_id": provider_id,
        "display_name": (payload.display_name or provider_id).strip(),
        "protocol": "openai",
        "enabled": bool(payload.enabled),
        "tags": [str(tag).strip() for tag in payload.tags if str(tag).strip()],
        "base_url": base_url,
        "model": model,
        "api_key_env": key_env,
    }

    if payload.timeout is not None:
        entry["timeout"] = payload.timeout
    if payload.max_tokens is not None:
        entry["max_tokens"] = payload.max_tokens
    if payload.temperature is not None:
        entry["temperature"] = payload.temperature

    return entry


@app.get("/api/providers/presets")
async def provider_presets():
    return _provider_presets()


@app.post("/api/providers")
async def create_provider(payload: ProviderInput):
    provider_id = payload.provider_id.strip().lower()

    if not _PROVIDER_ID_RE.fullmatch(provider_id):
        raise HTTPException(status_code=400, detail="provider_id 需为小写字母开头，仅含小写字母、数字、_ 或 -（2-32 位）")

    entries = _read_provider_entries()

    if any(str(item.get("provider_id")).lower() == provider_id for item in entries):
        raise HTTPException(status_code=400, detail=f"Provider 已存在：{provider_id}")

    entry = _build_provider_entry(payload, provider_id)
    entries.append(entry)
    _save_provider_entries(entries)

    if payload.api_key and payload.api_key.strip():
        _set_env_value(entry["api_key_env"], payload.api_key.strip())

    logger.info("新增 Provider: %s", provider_id)
    return {"ok": True, "provider": _get_provider_rows()}


@app.put("/api/providers/{provider_id}")
async def update_provider(provider_id: str, payload: ProviderInput):
    target = provider_id.strip().lower()
    entries = _read_provider_entries()
    index = next((i for i, item in enumerate(entries) if str(item.get("provider_id")).lower() == target), None)

    if index is None:
        raise HTTPException(status_code=404, detail=f"Provider 不存在：{target}")

    entry = _build_provider_entry(payload, target)
    entries[index] = entry
    _save_provider_entries(entries)

    if payload.api_key and payload.api_key.strip():
        _set_env_value(entry["api_key_env"], payload.api_key.strip())

    logger.info("更新 Provider: %s", target)
    return {"ok": True, "provider": _get_provider_rows()}


@app.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str):
    target = provider_id.strip().lower()
    entries = _read_provider_entries()
    remaining = [item for item in entries if str(item.get("provider_id")).lower() != target]

    if len(remaining) == len(entries):
        raise HTTPException(status_code=404, detail=f"Provider 不存在：{target}")

    _save_provider_entries(remaining)
    logger.info("删除 Provider: %s", target)
    return {"ok": True, "provider": _get_provider_rows()}


@app.post("/api/research")
async def create_research(request: ResearchRequest):
    raw_symbol = request.symbol.strip()

    resolved = _resolve_stock(raw_symbol)

    if not resolved["ok"]:
        raise HTTPException(
            status_code=400,
            detail=f"未找到该股票代码：{raw_symbol}",
        )

    symbol = resolved["symbol"]
    name = resolved["name"]

    job_id = str(uuid.uuid4())

    payload = request.model_dump()
    payload["symbol"] = symbol

    with _jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "symbol": symbol,
            "name": name,
            "status": "queued",
            "created_at": time.time(),
            "result": None,
            "error": None,
        }

    logger.info(
        "标的: %s(%s)",
        name,
        symbol,
    )

    _research_executor.submit(
        _run_research,
        job_id,
        payload,
    )

    logger.info("研究任务已提交: %s", job_id)

    return {
        "job_id": job_id,
        "symbol": symbol,
        "name": name,
        "status": "queued",
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    with _jobs_lock:
        job = jobs.get(job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        return dict(job)


@app.get("/api/files")
async def list_files():
    files: list[dict[str, Any]] = []

    for base_dir in (REPORTS_DIR, RESEARCH_DIR):
        if not base_dir.is_dir():
            continue

        try:
            for path in base_dir.rglob("*"):
                if not path.is_file():
                    continue

                if path.suffix.lower() not in (".json", ".md"):
                    continue

                try:
                    stat = path.stat()

                    files.append(
                        {
                            "path": str(
                                path.relative_to(PROJECT_ROOT)
                            ).replace("\\", "/"),
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                        }
                    )
                except OSError:
                    continue

        except OSError:
            logger.warning(
                "文件目录扫描失败: %s",
                base_dir,
                exc_info=True,
            )

    files.sort(
        key=lambda item: item["mtime"],
        reverse=True,
    )

    return files[:30]


@app.get("/api/files/{file_path:path}")
async def read_file(file_path: str):
    candidate = (PROJECT_ROOT / file_path).resolve()

    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    if candidate.suffix.lower() not in (".json", ".md"):
        raise HTTPException(
            status_code=403,
            detail="Unsupported file type",
        )

    if not candidate.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found",
        )

    try:
        content = candidate.read_text(
            encoding="utf-8",
            errors="replace",
        )

        return {
            "path": file_path,
            "content": content,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# New stock search endpoint
# ============================================================

@app.get("/api/search")
async def search_stocks(
    q: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=50),
):
    if not q.strip():
        return {
            "items": [],
            "error": "查询内容不能为空",
        }

    try:
        items = _search_stocks(q, limit)

        for item in items:
            name = item.get("name", "")
            if "\\u" in name:
                try:
                    item["name"] = json.loads('"' + name + '"')
                except (ValueError, TypeError):
                    pass

        return {
            "items": items,
        }

    except Exception as exc:
        logger.warning(
            "股票搜索失败: %s",
            exc,
            exc_info=True,
        )

        return {
            "items": [],
            "error": str(exc),
        }


# ============================================================
# New stock quote endpoint
# ============================================================

@app.get("/api/quote")
async def stock_quotes(
    symbols: str = Query(default=""),
):
    if not symbols.strip():
        return []

    requested = [
        item.strip()
        for item in symbols.split(",")
        if item.strip()
    ][:50]

    try:
        return _fetch_quotes(requested)

    except Exception:
        logger.warning(
            "批量行情请求失败",
            exc_info=True,
        )
        return []


# ============================================================
# New market indices endpoint
# ============================================================

@app.get("/api/indices")
async def market_indices():
    symbols = [
        "000001.SH",
        "399001.SZ",
        "399006.SZ",
        "000688.SH",
    ]

    try:
        return _fetch_quotes(symbols)

    except Exception:
        logger.warning(
            "指数行情请求失败",
            exc_info=True,
        )
        return []


# ============================================================
# New stock resolution endpoint
# ============================================================

@app.get("/api/resolve")
async def resolve_stock(
    symbol: str = Query(default=""),
):
    raw_value = symbol.strip()
    value = raw_value
    suffix = ""

    if "." in value:
        core, _, tail = value.partition(".")
        value = core.strip()
        suffix = tail.strip().upper()

    def not_found():
        return {
            "ok": False,
            "error": f"未找到该股票代码：{raw_value}",
        }

    if not value:
        return not_found()

    try:
        items = _search_stocks(value, limit=50)

        candidates = []

        for item in items:
            name = item.get("name", "")

            if "\\u" in name:
                try:
                    name = json.loads('"' + name + '"')
                except (ValueError, TypeError):
                    continue

            stock_type = str(item.get("type", "")).upper()

            if not stock_type.startswith("GP"):
                continue

            market = item.get("market", "").lower()
            code = str(item.get("code", "")).strip()

            if market not in ("sh", "sz", "bj"):
                continue

            if not re.fullmatch(r"\d{6}", code):
                continue

            if suffix and _symbol_from_market(market, code).split(".")[-1] != suffix:
                continue

            candidates.append({
                "code": code,
                "name": name,
                "symbol": _symbol_from_market(market, code),
            })

        # 纯数字：必须代码完全匹配
        if re.fullmatch(r"\d{5,6}", value):
            for item in candidates:
                if item["code"] == value:
                    return {
                        "ok": True,
                        "symbol": item["symbol"],
                        "name": item["name"],
                    }

            return not_found()

        # 中文或字母：只接受名称完全匹配或前缀匹配
        for item in candidates:
            if item["name"] == value:
                return {
                    "ok": True,
                    "symbol": item["symbol"],
                    "name": item["name"],
                }

        for item in candidates:
            if item["name"].startswith(value):
                return {
                    "ok": True,
                    "symbol": item["symbol"],
                    "name": item["name"],
                }

        if len(value) >= 2:
            for item in candidates:
                if value in item["name"]:
                    return {
                        "ok": True,
                        "symbol": item["symbol"],
                        "name": item["name"],
                    }

        return not_found()

    except Exception:
        logger.warning(
            "股票代码解析失败: %s",
            value,
            exc_info=True,
        )
        return not_found()


# ============================================================
# Application shutdown
# ============================================================

@app.on_event("shutdown")
def shutdown():
    _research_executor.shutdown(
        wait=False,
        cancel_futures=True,
    )