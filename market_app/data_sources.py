from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from .config import CACHE_DIR, SCREEN_CACHE_DIR

try:
    import baostock as bs
except Exception:  # pragma: no cover - handled at runtime
    bs = None


BEIJING = ZoneInfo("Asia/Shanghai")
HTTP_TIMEOUT = 15
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Referer": "https://gu.qq.com/", "Accept": "*/*"}

_cache_lock = threading.RLock()
_memory_cache: dict[str, tuple[float, Any]] = {}
_bs_lock = threading.RLock()
_bs_logged_in = False
_status_cache: tuple[float, list[dict[str, Any]]] | None = None

SOURCE_INFO = {
    "tencent_quote": {
        "id": "tencent_quote",
        "name": "腾讯财经 · 实时",
        "kind": "实时快照 / 分钟线",
        "endpoint": "qt.gtimg.cn",
        "license": "公开网页接口，非官方 API；个人自用",
        "note": "实时快照延迟通常在数秒内；无 SLA，字段可能变动。",
    },
    "tencent_kline": {
        "id": "tencent_kline",
        "name": "腾讯财经 · 日 K",
        "kind": "日/周/月前复权 K 线",
        "endpoint": "ifzq.gtimg.cn、web.ifzq.gtimg.cn",
        "license": "公开网页接口，非官方 API；个人自用",
        "note": "高频请求会被 WAF 返回 HTTP 501；失败时工作台自动改用本地缓存或 BaoStock。",
    },
    "baostock": {
        "id": "baostock",
        "name": "BaoStock",
        "kind": "历史日/周/月线、前复权、指数与 ETF",
        "endpoint": "baostock Python SDK",
        "license": "BSD License，免费、免 Token",
        "note": "历史数据权威性较好；不提供盘中实时。",
    },
    "eastmoney": {
        "id": "eastmoney",
        "name": "东方财富",
        "kind": "全市场行情、资金流、龙虎榜、基本面",
        "endpoint": "push2his.eastmoney.com",
        "license": "公开网页接口，非官方 API；个人自用",
        "note": "数据最全，但当前网络实测 502/连接中断，未作为主源。",
    },
    "ths": {
        "id": "ths",
        "name": "同花顺",
        "kind": "涨停原因、题材补充",
        "endpoint": "zx.10jqka.com.cn",
        "license": "公开网页接口，非官方 API；个人自用",
        "note": "仅用于涨停原因，不提供全量 K 线；可用性随网络变化。",
    },
}


class DataFetchError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------

def now_beijing() -> datetime:
    return datetime.now(BEIJING)


def now_text() -> str:
    return now_beijing().strftime("%Y-%m-%d %H:%M:%S")


def infer_market(code: str) -> str:
    code = str(code).strip()
    if code.startswith(("sh", "sz", "bj")):
        return code[:2].lower()
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith(("4", "8")):
        return "bj"
    return "sh"


def normalize_symbol(raw: str) -> str:
    """Return the canonical display symbol, e.g. 600519.SH or 000001.SZ."""

    text = str(raw or "").strip().upper().replace(" ", "")
    if not text:
        raise ValueError("股票代码不能为空")

    # 600519.SH / 600519.SH / SH600519 / sh.600519
    matched = re.fullmatch(r"(?:SH|SZ|BJ)?\.?(\d{5,6})(?:\.?(?:SH|SZ|BJ))?", text)
    if not matched:
        raise ValueError(f"无法识别股票代码: {raw}")

    code = matched.group(1)
    suffix = ""
    for part in re.findall(r"(?:SH|SZ|BJ)", text):
        suffix = part
        break

    market = suffix.lower() if suffix else infer_market(code)
    if market not in ("sh", "sz", "bj"):
        raise ValueError(f"无法识别市场: {raw}")
    return f"{code}.{market.upper()}"


def tencent_code(symbol: str) -> str:
    display = normalize_symbol(symbol)
    code, suffix = display.split(".")
    return f"{suffix.lower()}{code}"


def baostock_code(symbol: str) -> str:
    display = normalize_symbol(symbol)
    code, suffix = display.split(".")
    return f"{suffix.lower()}.{code}"


def code_only(symbol: str) -> str:
    return normalize_symbol(symbol).split(".")[0]


def is_index(symbol: str) -> bool:
    display = normalize_symbol(symbol)
    code, market = display.split(".")
    return (market == "SH" and code.startswith("000")) or (market == "SZ" and code.startswith("399"))


# ---------------------------------------------------------------------------
# Low-level HTTP and cache
# ---------------------------------------------------------------------------

def _http_get(url: str, *, timeout: int = HTTP_TIMEOUT, encoding: str | None = None, retries: int = 3) -> requests.Response:
    """GET with bounded retries for throttling and transient upstream 5xx.

    Tencent returns HTTP 501/429 when a backtest hammers it; without a retry
    the whole run aborts on one symbol. 404/403 are not retried because they
    are real answers, not transient noise.
    """

    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            response = requests.get(url, headers=_HEADERS, timeout=timeout)
            if response.status_code == 200:
                if encoding:
                    response.encoding = encoding
                return response
            if response.status_code in (429, 500, 501, 502, 503, 504):
                last_error = DataFetchError(f"HTTP {response.status_code}: {url}")
                if attempt < retries - 1:
                    time.sleep(0.6 * (2 ** attempt))
                    continue
                raise last_error
            raise DataFetchError(f"HTTP {response.status_code}: {url}")
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.6 * (2 ** attempt))
                continue
            raise DataFetchError(f"网络请求失败: {exc}") from exc
    raise DataFetchError(f"网络请求失败: {last_error}")


def _cache_get(key: str, ttl: float) -> Any | None:
    now = time.time()
    with _cache_lock:
        item = _memory_cache.get(key)
        if item and now - item[0] < ttl:
            return item[1]
    path = CACHE_DIR / f"{key}.json"
    if path.is_file() and now - path.stat().st_mtime < ttl:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            with _cache_lock:
                _memory_cache[key] = (path.stat().st_mtime, value)
            return value
        except Exception:
            return None
    return None


def _cache_set(key: str, value: Any) -> None:
    with _cache_lock:
        _memory_cache[key] = (time.time(), value)
    try:
        path = CACHE_DIR / f"{key}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tencent
# ---------------------------------------------------------------------------

def _parse_unquote_name(text: str) -> str:
    raw = text.strip()
    if "\\u" in raw:
        try:
            return json.loads('"' + raw + '"')
        except Exception:
            return raw
    return raw


def search_stocks(query: str, limit: int = 12) -> list[dict[str, Any]]:
    query = str(query or "").strip()
    if not query:
        return []

    url = "https://smartbox.gtimg.cn/s3/"
    response = requests.get(
        url, params={"q": query, "t": "all"}, headers=_HEADERS, timeout=10
    )
    if response.status_code != 200:
        raise DataFetchError(f"腾讯搜索 HTTP {response.status_code}")
    text = response.content.decode("gbk", errors="replace")
    match = re.search(r'v_hint\s*=\s*"([^"]*)"', text, re.IGNORECASE)
    if not match:
        return []

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in match.group(1).split("^"):
        fields = item.split("~")
        if len(fields) < 5:
            continue
        market = fields[0].strip().lower()
        code = fields[1].strip()
        name = _parse_unquote_name(fields[2])
        stock_type = fields[4].strip()
        if market not in ("sh", "sz", "bj") or not code.isdigit() or not name:
            continue
        symbol = f"{code}.{market.upper()}"
        if symbol in seen:
            continue
        seen.add(symbol)
        results.append({
            "symbol": symbol,
            "code": code,
            "market": market.upper(),
            "name": name,
            "type": stock_type,
            "type_label": _type_label(stock_type),
        })
        if len(results) >= limit:
            break
    return results


def _type_label(stock_type: str) -> str:
    if stock_type.startswith("GP"):
        return "A股" if "A" in stock_type else "股票"
    if stock_type == "ZS":
        return "指数"
    if stock_type == "ETF":
        return "ETF"
    if stock_type.startswith("QZ"):
        return "权证"
    return stock_type or "其它"


def resolve_symbol(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {"ok": False, "error": "请输入股票代码或名称"}

    try:
        display = normalize_symbol(text)
        found = search_stocks(code_only(display), limit=20)
        for item in found:
            if item["symbol"] == display:
                return {"ok": True, **item, "symbol": display}
        return {
            "ok": True,
            "symbol": display,
            "code": code_only(display),
            "market": display.split(".")[1],
            "name": display,
            "type": "GP-A",
            "type_label": "A股",
        }
    except ValueError:
        pass

    found = search_stocks(text, limit=20)
    stocks = [item for item in found if item["type"].startswith("GP") or item["type"] in ("ETF", "ZS")]
    if not stocks:
        return {"ok": False, "error": f"未找到标的：{text}"}
    return {"ok": True, **stocks[0]}


def _quote_from_fields(symbol: str, fields: list[str]) -> dict[str, Any] | None:
    if len(fields) < 46:
        return None
    name = fields[1].strip()
    if not name:
        return None

    def num(value: str, scale: float = 1.0) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not np.isfinite(number):
            return None
        return round(number * scale, 4)

    code, market = symbol.split(".")
    quote_time = fields[30].strip()
    timestamp = None
    if re.fullmatch(r"\d{14}", quote_time):
        timestamp = f"{quote_time[0:4]}-{quote_time[4:6]}-{quote_time[6:8]} {quote_time[8:10]}:{quote_time[10:12]}:{quote_time[12:14]}"

    return {
        "symbol": symbol,
        "code": code,
        "market": market,
        "name": name,
        "price": num(fields[3]),
        "prev_close": num(fields[4]),
        "open": num(fields[5]),
        "high": num(fields[33]),
        "low": num(fields[34]),
        "change": num(fields[31]),
        "change_pct": num(fields[32]),
        "volume": num(fields[6], 100.0),
        "amount": num(fields[37], 10000.0),
        "turnover": num(fields[38]),
        "pe_ttm": num(fields[39]),
        "market_cap": num(fields[44], 100000000.0),
        "time": timestamp or quote_time or None,
        "source": "腾讯财经 qt.gtimg.cn",
    }


def _quote_from_sina(symbol: str, raw: str) -> dict[str, Any] | None:
    fields = raw.split(",")
    if len(fields) < 32:
        return None

    def num(value: str, scale: float = 1.0) -> float | None:
        try:
            return round(float(value) * scale, 4)
        except (TypeError, ValueError):
            return None

    code, market = symbol.split(".")
    price = num(fields[3])
    prev_close = num(fields[2])
    change = round(price - prev_close, 4) if price is not None and prev_close not in (None, 0) else None
    change_pct = round(change / prev_close * 100, 4) if change is not None and prev_close else None
    timestamp = f"{fields[30]} {fields[31]}" if fields[30] and fields[31] else None
    return {
        "symbol": symbol,
        "code": code,
        "market": market,
        "name": fields[0].strip(),
        "price": price,
        "prev_close": prev_close,
        "open": num(fields[1]),
        "high": num(fields[4]),
        "low": num(fields[5]),
        "change": change,
        "change_pct": change_pct,
        "volume": num(fields[8]),
        "amount": num(fields[9]),
        "turnover": None,
        "pe_ttm": None,
        "market_cap": None,
        "time": timestamp,
        "source": "新浪财经 hq.sinajs.cn",
    }


def _get_sina_quotes(symbols: list[str]) -> list[dict[str, Any]]:
    query = ",".join(tencent_code(symbol) for symbol in symbols[:50])
    response = _http_get(
        f"https://hq.sinajs.cn/list={query}",
        timeout=8,
        encoding="gbk",
        retries=2,
    )
    text = response.text
    results: list[dict[str, Any]] = []
    for symbol in symbols[:50]:
        code = tencent_code(symbol)
        match = re.search(rf'hq_str_{re.escape(code)}\s*=\s*"([^"]*)"', text)
        if not match:
            continue
        item = _quote_from_sina(symbol, match.group(1))
        if item:
            results.append(item)
    return results


def get_quotes(symbols: list[str]) -> list[dict[str, Any]]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in symbols:
        try:
            symbol = normalize_symbol(raw)
        except ValueError:
            continue
        if symbol not in seen:
            seen.add(symbol)
            normalized.append(symbol)
    if not normalized:
        return []

    query = ",".join(tencent_code(symbol) for symbol in normalized[:50])
    try:
        response = _http_get(f"https://qt.gtimg.cn/q={query}", timeout=5, retries=1)
        text = response.content.decode("gbk", errors="replace")
        results: list[dict[str, Any]] = []
        for symbol in normalized[:50]:
            code = tencent_code(symbol)
            match = re.search(rf'v_{re.escape(code)}\s*=\s*"([^"]*)"', text)
            if not match:
                continue
            item = _quote_from_fields(symbol, match.group(1).split("~"))
            if item:
                results.append(item)
        if results:
            return results
    except Exception:
        pass
    # 腾讯 WAF 拦截 qt.gtimg.cn 时，用新浪行情兜底；字段和来源都会原样标出。
    try:
        return _get_sina_quotes(normalized)
    except Exception:
        return []


def get_quote(symbol: str) -> dict[str, Any] | None:
    values = get_quotes([symbol])
    return values[0] if values else None


def _tencent_row_to_frame(rows: list[list[Any]]) -> pd.DataFrame:
    cleaned = [row[:6] for row in rows if isinstance(row, list) and len(row) >= 6]
    frame = pd.DataFrame(cleaned, columns=["date", "open", "close", "high", "low", "volume"])
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    # 腾讯 K 线成交量单位是“手”，统一换成股。
    frame["volume"] = frame["volume"] * 100.0
    frame["amount"] = np.nan
    frame["pct_change"] = frame["close"].pct_change() * 100.0
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"]).reset_index(drop=True)
    return frame


def get_tencent_history(symbol: str, period: str = "day", bars: int = 640) -> tuple[pd.DataFrame, dict[str, Any]]:
    code = tencent_code(symbol)
    period = period if period in ("day", "week", "month") else "day"
    today = now_beijing().date()
    start = today - timedelta(days=365 * 8 if period != "day" else 365 * 4)
    param = f"{code},{period},{start.isoformat()},{today.isoformat()},{max(bars, 320)},qfq"
    last_error: Exception | None = None
    for host in ("https://ifzq.gtimg.cn", "https://web.ifzq.gtimg.cn"):
        url = f"{host}/appstock/app/fqkline/get?param={param}"
        try:
            response = _http_get(url, timeout=15)
            payload = response.json()
            item = payload.get("data", {}).get(code, {})
            rows = item.get(f"qfq{period}") or item.get(period) or []
            if not rows:
                raise DataFetchError(f"腾讯未返回 {symbol} 的 {period} K 线")
            frame = _tencent_row_to_frame(rows).tail(max(80, bars)).reset_index(drop=True)
            provenance = {
                "source": "腾讯财经",
                "endpoint": "ifzq.gtimg.cn fqkline",
                "adjust": "前复权",
                "rows": int(len(frame)),
                "as_of": str(frame["date"].iloc[-1]),
                "fetched_at": now_text(),
                "url": url,
                "note": "腾讯 K 线不含成交额，成交额列由 BaoStock 补；本页趋势指标只依赖 OHLCV。",
            }
            return frame, provenance
        except Exception as exc:
            last_error = exc
    raise DataFetchError(f"腾讯 K 线获取失败: {last_error}")


def get_tencent_minute(symbol: str, period: str = "m5", count: int = 320) -> tuple[pd.DataFrame, dict[str, Any]]:
    code = tencent_code(symbol)
    url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{period},,{count}"
    response = _http_get(url, timeout=15)
    payload = response.json()
    item = payload.get("data", {}).get(code, {})
    rows = item.get(period) or []
    if not rows:
        raise DataFetchError(f"腾讯未返回 {symbol} 的 {period} 数据")
    cleaned = []
    for row in rows:
        # 分钟行通常为 [time, open, close, high, low, volume]
        if isinstance(row, list) and len(row) >= 6:
            cleaned.append(row[:6])
    frame = pd.DataFrame(cleaned, columns=["date", "open", "close", "high", "low", "volume"])
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = frame["volume"] * 100.0
    frame["amount"] = np.nan
    frame["pct_change"] = frame["close"].pct_change() * 100.0
    return frame, {
        "source": "腾讯财经",
        "endpoint": "ifzq.gtimg.cn mkline",
        "rows": int(len(frame)),
        "as_of": str(frame["date"].iloc[-1]),
        "fetched_at": now_text(),
        "url": url,
    }


# ---------------------------------------------------------------------------
# BaoStock
# ---------------------------------------------------------------------------

def _ensure_baostock() -> None:
    global _bs_logged_in
    if bs is None:
        raise DataFetchError("未安装 baostock")
    with _bs_lock:
        if _bs_logged_in:
            return
        result = bs.login()
        if result.error_code != "0":
            raise DataFetchError(f"BaoStock 登录失败: {result.error_msg}")
        _bs_logged_in = True


def _reset_baostock() -> None:
    global _bs_logged_in
    with _bs_lock:
        try:
            bs.logout()
        except Exception:
            pass
        _bs_logged_in = False


def get_baostock_history(symbol: str, period: str = "day", bars: int = 640) -> tuple[pd.DataFrame, dict[str, Any]]:
    _ensure_baostock()
    code = baostock_code(symbol)
    frequency = {"day": "d", "week": "w", "month": "m"}.get(period, "d")
    today = now_beijing().date()
    start = today - timedelta(days=365 * 12 if period != "day" else 365 * 5)
    adjust = "3" if is_index(symbol) else "2"
    fields = "date,open,high,low,close,volume,amount,turn,pctChg"
    last_error: str | None = None
    result = None
    for attempt in range(2):
        try:
            _ensure_baostock()
            with _bs_lock:
                result = bs.query_history_k_data_plus(
                    code,
                    fields,
                    start_date=start.isoformat(),
                    end_date=today.isoformat(),
                    frequency=frequency,
                    adjustflag=adjust,
                )
            if result.error_code == "0":
                break
            last_error = result.error_msg
        except Exception as exc:
            last_error = str(exc)
        _reset_baostock()
    if result is None or result.error_code != "0":
        raise DataFetchError(f"BaoStock 查询失败: {last_error or '未知错误'}")
    rows = result.data or []
    if not rows:
        raise DataFetchError(f"BaoStock 未返回 {symbol} 的 {period} 数据")
    frame = pd.DataFrame(rows, columns=fields.split(","))
    for column in ("open", "high", "low", "close", "volume", "amount", "turn", "pctChg"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.rename(columns={"pctChg": "pct_change"})
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"]).reset_index(drop=True)
    frame = frame.tail(max(80, bars)).reset_index(drop=True)
    provenance = {
        "source": "BaoStock",
        "endpoint": "query_history_k_data_plus",
        "adjust": "不复权" if adjust == "3" else "前复权",
        "adjustflag": adjust,
        "rows": int(len(frame)),
        "as_of": str(frame["date"].iloc[-1]),
        "fetched_at": now_text(),
        "note": "成交量单位为股，成交额单位为元。",
    }
    return frame, provenance


# ---------------------------------------------------------------------------
# History facade with cache
# ---------------------------------------------------------------------------

def _sanitize_key(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", key)


def get_history(symbol: str, period: str = "day", bars: int = 320) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbol = normalize_symbol(symbol)
    period = period if period in ("day", "week", "month") else "day"
    bars = max(80, min(int(bars), 640))
    key = _sanitize_key(f"hist_baostock_{symbol}_{period}_{bars}")
    cached = _cache_get(key, 600)
    if cached:
        frame = pd.DataFrame(cached["rows"])
        for column in ("open", "high", "low", "close", "volume", "amount", "turn", "pct_change"):
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame, dict(cached["provenance"])

    errors: list[str] = []
    try:
        frame, provenance = get_tencent_history(symbol, period, bars)
        _cache_set(key, {"rows": frame.to_dict(orient="records"), "provenance": provenance})
        return frame, provenance
    except Exception as exc:
        errors.append(f"腾讯: {exc}")

    try:
        frame, provenance = get_baostock_history(symbol, period, bars)
        provenance["fallback"] = True
        provenance["fallback_reason"] = " | ".join(errors)
        _cache_set(key, {"rows": frame.to_dict(orient="records"), "provenance": provenance})
        return frame, provenance
    except Exception as exc:
        errors.append(f"BaoStock: {exc}")

    raise DataFetchError("；".join(errors))


def get_index_return_20(symbol: str = "000001.SH") -> float | None:
    try:
        frame, _ = get_history(symbol, "day", 140)
        if len(frame) < 21:
            return None
        return round((float(frame["close"].iloc[-1]) / float(frame["close"].iloc[-21]) - 1.0) * 100.0, 4)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Universes
# ---------------------------------------------------------------------------

def _bs_universe(function_name: str) -> list[dict[str, Any]]:
    _ensure_baostock()
    with _bs_lock:
        result = getattr(bs, function_name)()
    if result.error_code != "0":
        raise DataFetchError(f"BaoStock {function_name} 失败: {result.error_msg}")
    items: list[dict[str, Any]] = []
    for row in result.data or []:
        # [updateDate, code, code_name]
        if len(row) < 3:
            continue
        code = str(row[1])
        name = str(row[2])
        if "." not in code:
            continue
        market, number = code.split(".", 1)
        items.append({
            "symbol": f"{number}.{market.upper()}",
            "code": number,
            "market": market.upper(),
            "name": name,
            "type": "GP-A",
        })
    return items


def get_universe(name: str) -> list[dict[str, Any]]:
    key = f"universe_{name}"
    cached = _cache_get(key, 6 * 3600)
    if cached:
        return cached

    if name == "hs300":
        items = _bs_universe("query_hs300_stocks")
    elif name == "zz500":
        items = _bs_universe("query_zz500_stocks")
    elif name == "broad":
        hs300 = _bs_universe("query_hs300_stocks")
        zz500 = _bs_universe("query_zz500_stocks")
        by_symbol = {item["symbol"]: item for item in hs300}
        for item in zz500:
            by_symbol.setdefault(item["symbol"], item)
        items = list(by_symbol.values())
    else:
        raise ValueError(f"未知股票池: {name}")

    _cache_set(key, items)
    return items


# ---------------------------------------------------------------------------
# Source health
# ---------------------------------------------------------------------------

def _timed_check(identifier: str, name: str, function) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        detail = function()
        return {
            **SOURCE_INFO[identifier],
            "ok": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "detail": detail,
            "checked_at": now_text(),
        }
    except Exception as exc:
        return {
            **SOURCE_INFO[identifier],
            "ok": False,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc),
            "checked_at": now_text(),
        }


def _check_tencent_quote() -> str:
    quote = get_quote("000001.SH")
    if not quote:
        raise DataFetchError("未解析到上证指数")
    return f"上证指数 {quote['price']}，时间 {quote['time']}"


def _check_tencent_kline() -> str:
    code = tencent_code("600519.SH")
    today = now_beijing().date()
    start = today - timedelta(days=200)
    param = f"{code},day,{start.isoformat()},{today.isoformat()},120,qfq"
    url = f"https://ifzq.gtimg.cn/appstock/app/fqkline/get?param={param}"
    response = _http_get(url, timeout=8, retries=1)
    payload = response.json()
    item = payload.get("data", {}).get(code, {})
    rows = item.get("qfqday") or item.get("day") or []
    if not rows:
        raise DataFetchError("K 线返回为空")
    return f"600519.SH 最新 {rows[-1][0]}，返回 {len(rows)} 根"


def _check_baostock() -> str:
    frame, _ = get_baostock_history("600519.SH", "day", 20)
    return f"600519 最新 {frame['date'].iloc[-1]} 收盘 {float(frame['close'].iloc[-1]):.2f}"


def _check_eastmoney() -> str:
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        "secid=1.600519&fields1=f1,f2,f3,f4,f5,f6&"
        "fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=2&beg=20260101&end=20261120"
    )
    response = _http_get(url, timeout=6, retries=1)
    payload = response.json()
    if not payload.get("data", {}).get("klines"):
        raise DataFetchError("返回为空")
    return "K 线接口可用"


def _check_ths() -> str:
    day = now_beijing().date().isoformat()
    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/date/{day}/"
        "orderby/date/orderway/desc/charset/GBK/"
    )
    response = _http_get(url, timeout=6, retries=1)
    if response.status_code != 200:
        raise DataFetchError(f"HTTP {response.status_code}")
    return "涨停原因接口可用"


def get_source_status(refresh: bool = False) -> list[dict[str, Any]]:
    global _status_cache
    if not refresh and _status_cache and time.time() - _status_cache[0] < 300:
        return _status_cache[1]

    specs = [
        ("tencent_quote", "腾讯财经 · 实时", _check_tencent_quote),
        ("tencent_kline", "腾讯财经 · 日 K", _check_tencent_kline),
        ("baostock", "BaoStock", _check_baostock),
    ]
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="source-check") as pool:
        checks = list(pool.map(lambda spec: _timed_check(*spec), specs))
    _status_cache = (time.time(), checks)
    return checks
