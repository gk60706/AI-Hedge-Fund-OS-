from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

import requests

# 本机 IPv6 出网会先等待约 30 秒再回退 IPv4；强制 requests 走 IPv4。
try:
    from urllib3.util import connection as _urllib3_connection

    _urllib3_connection.HAS_IPV6 = False
except Exception:
    pass

from . import data_sources as ds

SINA_ENDPOINT = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
SINA_HEADERS = {
    "User-Agent": ds._UA,
    "Referer": "https://vip.stock.finance.sina.com.cn/",
    "Accept": "*/*",
}
EM_HEADERS = {
    "User-Agent": ds._UA,
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
}
EM_DATA_HEADERS = {
    "User-Agent": ds._UA,
    "Referer": "https://data.eastmoney.com/",
    "Accept": "*/*",
}

SINA_PAGE_SIZE = 100
SINA_PAGES = 56
CNINFO_ENDPOINT = "http://www.cninfo.com.cn/new/data/szse_stock.json"
TENCENT_BATCH_ENDPOINT = "https://qt.gtimg.cn/q="
TENCENT_BATCH_SIZE = 50

_lock = ds._cache_lock


class MarketDataError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _json_get(
    url: str,
    params: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: int = 12,
    retries: int = 1,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code != 200:
                raise MarketDataError(f"HTTP {response.status_code}")
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.8)
    raise MarketDataError(str(last_error))


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


# ---------------------------------------------------------------------------
# Full A-share snapshot (Sina)
# ---------------------------------------------------------------------------

def _sina_page(page: int) -> list[dict[str, Any]]:
    payload = _json_get(
        SINA_ENDPOINT,
        {
            "page": str(page),
            "num": str(SINA_PAGE_SIZE),
            "sort": "changepercent",
            "asc": "0",
            "node": "hs_a",
            "symbol": "",
            "_s_r_a": "page",
        },
        headers=SINA_HEADERS,
        timeout=12,
        retries=1,
    )
    if not isinstance(payload, list):
        return []
    return payload


def _board_of(code: str, name: str) -> str:
    if "ST" in name.upper():
        return "ST"
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith("688"):
        return "科创板"
    if code.startswith(("4", "8", "92")):
        return "北交所"
    return "主板"


def _limit_pct(code: str, name: str) -> float:
    if "ST" in name.upper():
        return 5.0
    if code.startswith(("300", "301", "688")):
        return 20.0
    if code.startswith(("4", "8", "92")):
        return 30.0
    return 10.0


def _sina_item(row: dict[str, Any]) -> dict[str, Any] | None:
    raw_symbol = str(row.get("symbol") or "").strip().lower()
    code = str(row.get("code") or "").strip()
    name = str(row.get("name") or "").strip()
    if len(raw_symbol) < 6 or not code or not name:
        return None
    market = raw_symbol[:2].upper()
    if market not in ("SH", "SZ", "BJ"):
        return None
    price = _to_float(row.get("trade"))
    pct = _to_float(row.get("changepercent"))
    amount = _to_float(row.get("amount"))
    market_cap = _to_float(row.get("mktcap"))
    float_cap = _to_float(row.get("nmc"))
    turnover = _to_float(row.get("turnoverratio"))
    pe = _to_float(row.get("per"))
    pb = _to_float(row.get("pb"))
    board = _board_of(code, name)
    return {
        "symbol": f"{code}.{market}",
        "code": code,
        "name": name,
        "market": market,
        "board": board,
        "price": _round(price, 3),
        "pct": _round(pct, 2),
        "amount": amount,
        "turnover": _round(turnover, 2),
        "pe": _round(pe, 2),
        "pb": _round(pb, 2),
        "market_cap_yi": _round(market_cap / 10000.0 if market_cap else None, 2),
        "float_cap_yi": _round(float_cap / 10000.0 if float_cap else None, 2),
        "limit_pct": _limit_pct(code, name),
        "is_st": "ST" in name.upper(),
        "ticktime": str(row.get("ticktime") or ""),
        "valid": bool(price and price > 0),
    }


def _market_of_code(code: str) -> str | None:
    if code.startswith("6"):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("920", "8", "4")):
        return "BJ"
    return None


def _cninfo_symbols() -> list[dict[str, str]]:
    cached = ds._cache_get("cninfo_a_codes_v1", 86400)
    if cached:
        return cached
    payload = _json_get(
        CNINFO_ENDPOINT,
        {},
        headers={"User-Agent": ds._UA, "Accept": "*/*"},
        timeout=12,
        retries=2,
    )
    rows = payload.get("stockList") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise MarketDataError("巨潮 A 股代码表返回结构异常")

    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or str(row.get("category") or "") != "A股":
            continue
        code = str(row.get("code") or "").strip()
        name = str(row.get("zwjc") or "").strip()
        market = _market_of_code(code)
        if len(code) != 6 or not name or not market or code in seen:
            continue
        seen.add(code)
        items.append({"symbol": f"{code}.{market}", "code": code, "name": name, "market": market})

    if len(items) < 500:
        raise MarketDataError(f"巨潮 A 股代码表不足：{len(items)} 只")
    ds._cache_set("cninfo_a_codes_v1", items)
    return items


def _tencent_batch(chunk: list[str]) -> list[dict[str, Any]]:
    response = requests.get(
        TENCENT_BATCH_ENDPOINT + ",".join(chunk),
        headers={
            "User-Agent": ds._UA,
            "Referer": "https://gu.qq.com/",
            "Accept": "*/*",
        },
        timeout=12,
    )
    if response.status_code != 200:
        raise MarketDataError(f"腾讯批量行情 HTTP {response.status_code}")
    text = response.content.decode("gbk", "ignore")
    quotes: list[dict[str, Any]] = []
    for segment in text.split(";"):
        if '="' not in segment or "~" not in segment:
            continue
        key, body = segment.split('="', 1)
        body = body.rstrip('"').strip()
        fields = body.split("~")
        if len(fields) < 46:
            continue
        raw = key.strip().split("_")[-1]
        if len(raw) < 8:
            continue
        market = raw[:2].upper()
        code = raw[2:]
        if market not in ("SH", "SZ", "BJ"):
            continue
        quote = ds._quote_from_fields(f"{code}.{market}", fields)
        if not quote or not quote.get("price"):
            continue
        quotes.append(quote)
    return quotes


def _tencent_item(quote: dict[str, Any]) -> dict[str, Any]:
    symbol = str(quote.get("symbol") or "")
    code, market = symbol.split(".")
    name = str(quote.get("name") or "").strip()
    price = _to_float(quote.get("price"))
    market_cap = _to_float(quote.get("market_cap"))
    float_cap = _to_float(quote.get("float_market_cap"))
    return {
        "symbol": symbol,
        "code": code,
        "name": name,
        "market": market,
        "board": _board_of(code, name),
        "price": _round(price, 3),
        "pct": _round(_to_float(quote.get("change_pct")), 2),
        "amount": _to_float(quote.get("amount")),
        "turnover": _round(_to_float(quote.get("turnover")), 2),
        "pe": _round(_to_float(quote.get("pe_ttm")), 2),
        "pb": _round(_to_float(quote.get("pb")), 2),
        "market_cap_yi": _round(market_cap / 100000000.0 if market_cap else None, 2),
        "float_cap_yi": _round(float_cap / 100000000.0 if float_cap else None, 2),
        "limit_pct": _limit_pct(code, name),
        "is_st": "ST" in name.upper(),
        "ticktime": str(quote.get("time") or ""),
        "valid": bool(price and price > 0),
    }


def _sina_snapshot() -> dict[str, Any]:
    pages: dict[int, list[dict[str, Any]]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="sina-snapshot") as pool:
        futures = {pool.submit(_sina_page, page): page for page in range(1, SINA_PAGES + 1)}
        for future, page in futures.items():
            try:
                pages[page] = future.result(timeout=20)
            except Exception as exc:
                errors.append(f"page {page}: {str(exc)[:80]}")

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in sorted(pages):
        for row in pages[page]:
            item = _sina_item(row)
            if not item or item["symbol"] in seen:
                continue
            seen.add(item["symbol"])
            items.append(item)

    if len(items) < 500:
        raise MarketDataError(
            f"新浪全市场快照不足：{len(items)} 只；失败页 {len(errors)}/{SINA_PAGES}"
        )

    return {
        "ok": True,
        "items": items,
        "count": len(items),
        "coverage": {
            "pages_total": SINA_PAGES,
            "pages_ok": len(pages),
            "page_size": SINA_PAGE_SIZE,
            "errors": errors[:5],
            "note": "新浪 hs_a 分页快照；盘中按涨跌幅排序会变化，跨页可能有少量重复或漏项。",
        },
        "fetched_at": ds.now_text(),
        "source": "新浪财经 Market_Center.getHQNodeData",
    }


def market_snapshot(force: bool = False) -> dict[str, Any]:
    cached = None if force else ds._cache_get("market_snapshot_v2", 240)
    if cached:
        return cached

    errors: list[str] = []
    try:
        codes = _cninfo_symbols()
        chunks = [codes[index:index + TENCENT_BATCH_SIZE] for index in range(0, len(codes), TENCENT_BATCH_SIZE)]
        quotes: list[dict[str, Any]] = []
        failed = 0
        with ThreadPoolExecutor(max_workers=10, thread_name_prefix="tencent-snapshot") as pool:
            futures = {
                pool.submit(_tencent_batch, [ds.tencent_code(row["symbol"]) for row in chunk]): number
                for number, chunk in enumerate(chunks, start=1)
            }
            for future, number in futures.items():
                try:
                    quotes.extend(future.result(timeout=20))
                except Exception as exc:
                    failed += 1
                    errors.append(f"batch {number}: {str(exc)[:80]}")

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for quote in quotes:
            item = _tencent_item(quote)
            if not item["symbol"] or item["symbol"] in seen:
                continue
            seen.add(item["symbol"])
            items.append(item)

        if len(items) >= 500:
            result = {
                "ok": True,
                "items": items,
                "count": len(items),
                "coverage": {
                    "codes_total": len(codes),
                    "quotes_ok": len(items),
                    "pages_total": len(chunks),
                    "pages_ok": len(chunks) - failed,
                    "page_size": TENCENT_BATCH_SIZE,
                    "errors": errors[:5],
                    "note": "巨潮 A 股代码表 + 腾讯批量行情；停牌/无报价会缺失，盘中约 4–8 秒刷新。",
                },
                "fetched_at": ds.now_text(),
                "source": "巨潮资讯 A 股代码表 + 腾讯财经 qt.gtimg.cn 批量行情",
            }
            ds._cache_set("market_snapshot_v2", result)
            return result
        errors.append(f"腾讯批量行情有效报价不足：{len(items)}")
    except Exception as exc:
        errors.append(f"腾讯批量行情失败：{str(exc)[:100]}")

    result = _sina_snapshot()
    result["coverage"]["fallback_reason"] = " | ".join(errors[:5])
    ds._cache_set("market_snapshot_v2", result)
    return result



# ---------------------------------------------------------------------------
# Latest trading day
# ---------------------------------------------------------------------------

def latest_trade_date() -> dict[str, Any]:
    cached = ds._cache_get("latest_trade_date_v1", 60)
    if cached:
        return cached

    result: dict[str, Any] = {
        "date": None,
        "source": "未知",
        "quote_time": None,
    }
    quote = ds.get_quote("000001.SH")
    if quote and quote.get("time"):
        text = str(quote["time"])
        result.update({
            "date": text[:10],
            "quote_time": text,
            "source": "腾讯/新浪指数快照时间",
        })
    else:
        try:
            rows = _fflow_raw("1.600519")
            if rows:
                result.update({
                    "date": rows[-1]["date"],
                    "source": "东方财富 600519 日资金流最后一日",
                })
        except Exception:
            pass

    if not result["date"]:
        today = ds.now_beijing().date()
        probe = today
        for _ in range(12):
            if probe.weekday() < 5:
                result.update({"date": probe.isoformat(), "source": "工作日推算（未核验交易日历）"})
                break
            probe -= timedelta(days=1)

    ds._cache_set("latest_trade_date_v1", result)
    return result


# ---------------------------------------------------------------------------
# Limit-up / limit-down / broken-board pools
# ---------------------------------------------------------------------------

def _date_arg(value: str | None) -> str:
    if value:
        return value.replace("-", "")[:8]
    latest = latest_trade_date().get("date")
    if latest:
        return latest.replace("-", "")
    return ds.now_beijing().strftime("%Y%m%d")


def _time_arg(value: Any) -> str | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    text = f"{number:06d}"
    return f"{text[0:2]}:{text[2:4]}:{text[4:6]}"


def _pool(kind: str, trade_date: str | None = None, page_size: int = 100) -> dict[str, Any]:
    url = {
        "zt": "https://push2ex.eastmoney.com/getTopicZTPool",
        "dt": "https://push2ex.eastmoney.com/getTopicDTPool",
        "zb": "https://push2ex.eastmoney.com/getTopicZBPool",
    }[kind]
    params = {
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": str(page_size),
        "sort": "fbt:asc",
        "date": _date_arg(trade_date),
    }
    cache_key = f"pool_{kind}_{params['date']}_{page_size}"
    cached = ds._cache_get(cache_key, 300)
    if cached:
        return cached
    try:
        payload = _json_get(url, params, headers=EM_HEADERS, timeout=12, retries=1)
    except Exception as exc:
        result = {"ok": False, "count": 0, "items": [], "error": str(exc)[:160], "date": params["date"]}
        ds._cache_set(cache_key, result)
        return result
    data = payload.get("data") or {}
    raw_items = data.get("pool") or []
    items: list[dict[str, Any]] = []
    for row in raw_items:
        code = str(row.get("c") or "")
        name = str(row.get("n") or "")
        price = _to_float(row.get("p"))
        item = {
            "symbol": f"{code}.{('SH' if str(row.get('m')) == '1' else 'SZ')}",
            "code": code,
            "name": name,
            "pct": _round(_to_float(row.get("zdp")), 2),
            "price": _round(price / 1000.0 if price else None, 3),
            "amount": _to_float(row.get("amount")),
            "float_cap_yi": _round((_to_float(row.get("ltsz")) or 0) / 1e8, 2),
            "turnover": _round(_to_float(row.get("hs")), 2),
            "streak": int(row.get("lbc") or row.get("days") or 0),
            "first_seal": _time_arg(row.get("fbt")),
            "last_seal": _time_arg(row.get("lbt")),
            "seal_fund_yi": _round((_to_float(row.get("fund")) or 0) / 1e8, 2),
            "broken_times": int(row.get("zbc") or 0),
            "industry": str(row.get("hybk") or ""),
            "stat": (row.get("zttj") or {}).get("days_text") if isinstance(row.get("zttj"), dict) else None,
            "days": int(row.get("zttj", {}).get("days") or 0) if isinstance(row.get("zttj"), dict) else 0,
            "count": int(row.get("zttj", {}).get("ct") or 0) if isinstance(row.get("zttj"), dict) else 0,
        }
        if kind == "zt" and item["days"] and item["count"]:
            item["stat"] = f"{item['days']}天{item['count']}板"
        items.append(item)

    result = {
        "ok": True,
        "count": int(data.get("tc") or len(items)),
        "date": params["date"],
        "items": items,
        "source": "东方财富涨停/跌停/炸板池",
    }
    ds._cache_set(cache_key, result)
    return result


def limit_up_pool(trade_date: str | None = None) -> dict[str, Any]:
    return _pool("zt", trade_date)


def limit_down_pool(trade_date: str | None = None) -> dict[str, Any]:
    return _pool("dt", trade_date)


def broken_board_pool(trade_date: str | None = None) -> dict[str, Any]:
    return _pool("zb", trade_date)


# ---------------------------------------------------------------------------
# Dragon-tiger list
# ---------------------------------------------------------------------------

def _lhb_query(day: str, limit: int) -> dict[str, Any]:
    params = {
        "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
        "columns": "ALL",
        "filter": f"(TRADE_DATE='{day}')",
        "pageNumber": "1",
        "pageSize": str(limit),
        "sortColumns": "BILLBOARD_NET_AMT",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    payload = _json_get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params,
        headers=EM_DATA_HEADERS,
        timeout=15,
        retries=1,
    )
    data = (payload.get("result") or {}).get("data") or []
    items = []
    for row in data:
        items.append({
            "code": str(row.get("SECURITY_CODE") or ""),
            "name": str(row.get("SECURITY_NAME_ABBR") or ""),
            "price": _round(_to_float(row.get("CLOSE_PRICE")), 2),
            "pct": _round(_to_float(row.get("CHANGE_RATE")), 2),
            "net_buy_yi": _round((_to_float(row.get("BILLBOARD_NET_AMT")) or 0) / 1e8, 2),
            "buy_yi": _round((_to_float(row.get("BILLBOARD_BUY_AMT")) or 0) / 1e8, 2),
            "sell_yi": _round((_to_float(row.get("BILLBOARD_SELL_AMT")) or 0) / 1e8, 2),
            "reason": str(row.get("EXPLAIN") or row.get("EXPLANATION") or ""),
        })
    return {"items": items, "pages": (payload.get("result") or {}).get("pages")}


def dragon_tiger(trade_date: str | None = None, limit: int = 20) -> dict[str, Any]:
    day = trade_date or latest_trade_date().get("date") or ds.now_beijing().date().isoformat()
    cache_key = f"lhb_v2_{day}_{limit}"
    cached = ds._cache_get(cache_key, 600)
    if cached:
        return cached

    try:
        payload = _lhb_query(day, limit)
        items = payload["items"]
        # 盘中当日龙虎榜尚未发布：回退到上一个工作日，并明确标注日期。
        if not items:
            probe = date.fromisoformat(day) - timedelta(days=1)
            for _ in range(7):
                if probe.weekday() < 5:
                    try:
                        candidate = _lhb_query(probe.isoformat(), limit)
                    except Exception:
                        candidate = {"items": []}
                    if candidate["items"]:
                        day = probe.isoformat()
                        items = candidate["items"]
                        payload = candidate
                        break
                probe -= timedelta(days=1)
    except Exception as exc:
        result = {"ok": False, "date": day, "items": [], "error": str(exc)[:160]}
        ds._cache_set(cache_key, result)
        return result

    result = {
        "ok": True,
        "date": day,
        "items": items,
        "pages": payload.get("pages"),
        "count": len(items),
        "source": "东方财富龙虎榜",
        "note": "当天龙虎榜通常在收盘后发布；盘中自动回退到最近一个有数据的交易日。",
    }
    if items:
        ds._cache_set(cache_key, result)
    return result



# ---------------------------------------------------------------------------
# Sector fund flow (best effort)
# ---------------------------------------------------------------------------

def sector_flow(limit: int = 8) -> dict[str, Any]:
    cached = ds._cache_get("sector_flow_v1", 180)
    if cached:
        return cached
    params = {
        "pn": "1",
        "pz": str(limit),
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f12,f14,f2,f3,f62,f184,f204,f205,f124",
    }
    try:
        inflow_payload = _json_get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params,
            headers=EM_HEADERS,
            timeout=10,
            retries=1,
        )
    except Exception as exc:
        result = {
            "ok": False,
            "error": str(exc)[:160],
            "inflow": [],
            "outflow": [],
            "note": "东方财富板块资金流 clist 接口当前被断开；不影响涨跌家数、涨停池和全市场雷达。",
        }
        ds._cache_set("sector_flow_v1", result)
        return result

    def parse(payload: dict[str, Any]) -> list[dict[str, Any]]:
        diff = (payload.get("data") or {}).get("diff") or []
        rows = []
        for row in diff:
            rows.append({
                "code": str(row.get("f12") or ""),
                "name": str(row.get("f14") or ""),
                "pct": _round(_to_float(row.get("f3")), 2),
                "main_net_yi": _round((_to_float(row.get("f62")) or 0) / 1e8, 2),
                "main_pct": _round(_to_float(row.get("f184")), 2),
                "leader": str(row.get("f204") or ""),
                "leader_code": str(row.get("f205") or ""),
            })
        return rows

    inflow = parse(inflow_payload)
    outflow_params = dict(params, po="0")
    try:
        outflow_payload = _json_get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            outflow_params,
            headers=EM_HEADERS,
            timeout=10,
            retries=1,
        )
        outflow = parse(outflow_payload)
    except Exception:
        outflow = []

    result = {
        "ok": bool(inflow),
        "inflow": inflow,
        "outflow": outflow,
        "error": None if inflow else "板块资金流返回为空",
        "note": "主力净流入是平台算法估算，只做观察，不进入趋势评分。",
    }
    ds._cache_set("sector_flow_v1", result)
    return result


# ---------------------------------------------------------------------------
# Market sentiment bundle
# ---------------------------------------------------------------------------

def market_sentiment(force: bool = False) -> dict[str, Any]:
    snapshot = market_snapshot(force=force)
    latest = latest_trade_date()
    trade_date = latest.get("date") or ds.now_beijing().date().isoformat()

    zt = limit_up_pool(trade_date)
    dt = limit_down_pool(trade_date)
    zb = broken_board_pool(trade_date)
    lhb = dragon_tiger(limit=16)
    sectors = sector_flow()

    valid = [item for item in snapshot["items"] if item["valid"] and item["pct"] is not None]
    up = sum(1 for item in valid if item["pct"] > 0)
    down = sum(1 for item in valid if item["pct"] < 0)
    flat = len(valid) - up - down
    strong_up = sum(1 for item in valid if item["pct"] >= 5)
    strong_down = sum(1 for item in valid if item["pct"] <= -5)
    amount_yi = sum((item["amount"] or 0) for item in valid) / 1e8
    pcts = sorted(item["pct"] for item in valid)
    median_pct = pcts[len(pcts) // 2] if pcts else None

    zt_count = int(zt.get("count") or 0)
    zb_count = int(zb.get("count") or 0)
    seal_rate = round(zt_count / max(1, zt_count + zb_count) * 100, 1)
    max_streak = max((item["streak"] for item in zt.get("items", [])), default=0)

    zt_items = sorted(
        zt.get("items", []),
        key=lambda item: (-item.get("streak", 0), item.get("first_seal") or "99:99:99"),
    )
    dt_items = sorted(dt.get("items", []), key=lambda item: item.get("pct") or 0)
    dt_count = int(dt.get("count") or 0)
    if not dt_items:
        derived = [
            {
                "symbol": item["symbol"],
                "code": item["code"],
                "name": item["name"],
                "pct": item["pct"],
                "price": item["price"],
                "amount": item["amount"],
                "turnover": item["turnover"],
                "float_cap_yi": item["float_cap_yi"],
                "industry": "",
                "seal_fund_yi": None,
                "note": "由全市场快照按板块跌停阈值估算",
            }
            for item in valid
            if not item["is_st"] and item["pct"] is not None and item["pct"] <= -(item["limit_pct"] - 0.1)
        ]
        dt_items = sorted(derived, key=lambda item: item.get("pct") or 0)
        dt_count = max(dt_count, len(dt_items))

    return {
        "ok": True,
        "as_of": trade_date,
        "as_of_source": latest.get("source"),
        "quote_time": latest.get("quote_time"),
        "fetched_at": ds.now_text(),
        "coverage": snapshot["coverage"],
        "breadth": {
            "total": len(valid),
            "up": up,
            "down": down,
            "flat": flat,
            "strong_up": strong_up,
            "strong_down": strong_down,
            "median_pct": median_pct,
            "amount_yi": round(amount_yi, 2),
            "limit_up_pct": round(sum(1 for item in valid if item["pct"] >= item["limit_pct"] - 0.2) / max(1, len(valid)) * 100, 2),
        },
        "limit_up": {
            "count": zt_count,
            "max_streak": max_streak,
            "seal_rate": seal_rate,
            "broken_count": zb_count,
            "items": zt_items[:30],
            "error": zt.get("error"),
        },
        "limit_down": {
            "count": dt_count,
            "items": dt_items[:12],
            "error": dt.get("error"),
            "note": "东方财富跌停池盘中偶尔只给数量不给明细；缺失时按全市场快照的板块跌停阈值估算。",
        },
        "broken_board": {
            "count": zb_count,
            "items": zb.get("items", [])[:12],
            "error": zb.get("error"),
        },
        "dragon_tiger": lhb,
        "sectors": sectors,
        "notes": [
            "涨跌家数来自巨潮 A 股代码表 + 腾讯批量行情，停牌/无报价个股会缺失。",
            "涨停/跌停判定受 ST、板块涨跌幅规则和停复牌影响，页面按板块规则估算，池子数量以东方财富当日池为准。",
            "主力净流入为平台算法估算，跨来源口径可能不同，只做观察，不进入策略评分。",
        ],
    }


# ---------------------------------------------------------------------------
# Full-market radar filter
# ---------------------------------------------------------------------------

def radar_query(
    *,
    q: str = "",
    board: str = "all",
    min_pct: float | None = None,
    max_pct: float | None = None,
    min_turnover: float | None = None,
    max_turnover: float | None = None,
    min_amount_yi: float | None = None,
    max_amount_yi: float | None = None,
    min_cap_yi: float | None = None,
    max_cap_yi: float | None = None,
    min_pe: float | None = None,
    max_pe: float | None = None,
    min_pb: float | None = None,
    max_pb: float | None = None,
    exclude_st: bool = True,
    sort: str = "pct",
    order: str = "desc",
    limit: int = 120,
) -> dict[str, Any]:
    snapshot = market_snapshot()
    query = q.strip().upper()
    items = snapshot["items"]

    def in_range(value: float | None, low: float | None, high: float | None) -> bool:
        if low is None and high is None:
            return True
        if value is None:
            return False
        if low is not None and value < low:
            return False
        if high is not None and value > high:
            return False
        return True

    filtered = []
    for item in items:
        if not item["valid"]:
            continue
        if board != "all" and item["board"] != board:
            continue
        if exclude_st and item["is_st"]:
            continue
        if query and query not in item["code"].upper() and query not in item["name"].upper():
            continue
        if not in_range(item["pct"], min_pct, max_pct):
            continue
        if not in_range(item["turnover"], min_turnover, max_turnover):
            continue
        if not in_range(item["amount"] / 1e8 if item["amount"] else None, min_amount_yi, max_amount_yi):
            continue
        if not in_range(item["market_cap_yi"], min_cap_yi, max_cap_yi):
            continue
        if not in_range(item["pe"], min_pe, max_pe):
            continue
        if not in_range(item["pb"], min_pb, max_pb):
            continue
        filtered.append(item)

    sort_key = {
        "pct": lambda item: item["pct"] if item["pct"] is not None else -999,
        "turnover": lambda item: item["turnover"] if item["turnover"] is not None else -1,
        "amount": lambda item: item["amount"] if item["amount"] is not None else -1,
        "cap": lambda item: item["market_cap_yi"] if item["market_cap_yi"] is not None else -1,
        "pe": lambda item: item["pe"] if item["pe"] is not None else 1e12,
        "pb": lambda item: item["pb"] if item["pb"] is not None else 1e12,
        "code": lambda item: item["code"],
    }.get(sort, lambda item: item["pct"] if item["pct"] is not None else -999)
    reverse = order != "asc"
    filtered.sort(key=sort_key, reverse=reverse)
    result_items = filtered[: max(1, min(limit, 300))]

    return {
        "ok": True,
        "as_of": latest_trade_date().get("date"),
        "total": len(items),
        "matched": len(filtered),
        "displayed": len(result_items),
        "coverage": snapshot["coverage"],
        "items": result_items,
        "fetched_at": ds.now_text(),
        "note": "全市场快照雷达只做筛选与展示，不生成买卖建议。",
    }


# ---------------------------------------------------------------------------
# Stock profile and fund flow
# ---------------------------------------------------------------------------

def _secid(symbol: str) -> tuple[str, str]:
    display = ds.normalize_symbol(symbol)
    code, market = display.split(".")
    return code, f"{'1' if market == 'SH' else '0'}.{code}"


def _fflow_raw(secid: str) -> list[dict[str, Any]]:
    cache_key = f"fflow_{secid.replace('.', '_')}"
    cached = ds._cache_get(cache_key, 300)
    if cached is not None:
        return cached
    params = {
        "lmt": "0",
        "klt": "101",
        "secid": secid,
        "ut": "b288e3eb9b7d4b6eb9d2f8d9b1c7ff9c",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
    }
    payload = _json_get(
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
        params,
        headers=EM_HEADERS,
        timeout=15,
        retries=1,
    )
    lines = (payload.get("data") or {}).get("klines") or []
    rows = []
    for line in lines:
        parts = str(line).split(",")
        if len(parts) < 13:
            continue
        rows.append({
            "date": parts[0],
            "main_net": _to_float(parts[1]),
            "small_net": _to_float(parts[2]),
            "mid_net": _to_float(parts[3]),
            "large_net": _to_float(parts[4]),
            "xlarge_net": _to_float(parts[5]),
            "main_pct": _to_float(parts[6]),
            "small_pct": _to_float(parts[7]),
            "mid_pct": _to_float(parts[8]),
            "large_pct": _to_float(parts[9]),
            "xlarge_pct": _to_float(parts[10]),
            "close": _to_float(parts[11]),
            "pct": _to_float(parts[12]),
        })
    ds._cache_set(cache_key, rows)
    return rows


def stock_flow(symbol: str, days: int = 20) -> dict[str, Any]:
    code, secid = _secid(symbol)
    days = max(1, min(int(days), 60))
    try:
        rows = _fflow_raw(secid)
    except Exception as exc:
        return {"ok": False, "symbol": ds.normalize_symbol(symbol), "error": str(exc)[:160], "items": []}
    if not rows:
        return {"ok": False, "symbol": ds.normalize_symbol(symbol), "error": "资金流返回为空", "items": []}
    tail = rows[-days:]
    items = [{
        "date": row["date"],
        "main_net_yi": _round((row["main_net"] or 0) / 1e8, 2),
        "main_pct": _round(row["main_pct"], 2),
        "close": _round(row["close"], 2),
        "pct": _round(row["pct"], 2),
    } for row in tail]
    return {
        "ok": True,
        "symbol": ds.normalize_symbol(symbol),
        "code": code,
        "days": len(items),
        "items": items,
        "summary": {
            "last_date": items[-1]["date"] if items else None,
            "last_main_net_yi": items[-1]["main_net_yi"] if items else None,
            "sum5_yi": round(sum(item["main_net_yi"] for item in items[-5:]), 2),
            "sum10_yi": round(sum(item["main_net_yi"] for item in items[-10:]), 2),
            "sum20_yi": round(sum(item["main_net_yi"] for item in items[-20:]), 2),
        },
        "note": "东方财富主力净流入为平台算法估算，跨来源口径可能不同；只做观察，不进入策略评分。",
        "source": "东方财富 push2his 日度资金流",
    }


def stock_profile(symbol: str) -> dict[str, Any]:
    display = ds.normalize_symbol(symbol)
    code, secid = _secid(display)
    quote = ds.get_quote(display) or {}
    profile: dict[str, Any] = {
        "ok": True,
        "symbol": display,
        "code": code,
        "name": quote.get("name") or display,
        "price": quote.get("price"),
        "pct": quote.get("change_pct"),
        "turnover": quote.get("turnover"),
        "amount": quote.get("amount"),
        "pe_ttm": quote.get("pe_ttm"),
        "pe_dynamic": quote.get("pe_dynamic"),
        "pb": quote.get("pb"),
        "market_cap": quote.get("market_cap"),
        "float_market_cap": quote.get("float_market_cap"),
        "market_cap_yi": _round((quote.get("market_cap") or 0) / 1e8, 2) if quote.get("market_cap") else None,
        "float_cap_yi": _round((quote.get("float_market_cap") or 0) / 1e8, 2) if quote.get("float_market_cap") else None,
        "industry": None,
        "region": None,
        "concepts": [],
        "industry_source": None,
        "sources": [quote.get("source")] if quote.get("source") else [],
        "notes": [],
    }

    em_params = {
        "secid": secid,
        "fltt": "2",
        "fields": "f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f127,f128,f129",
    }
    try:
        payload = _json_get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            em_params,
            headers=EM_HEADERS,
            timeout=8,
            retries=1,
        )
        data = payload.get("data") or {}
        if data:
            profile.update({
                "name": str(data.get("f58") or profile["name"]),
                "price": _round(_to_float(data.get("f43")), 3) or profile["price"],
                "pct": _round(_to_float(data.get("f170")), 2),
                "turnover": _round(_to_float(data.get("f168")), 2),
                "pe_ttm": _round(_to_float(data.get("f162")), 2),
                "pb": _round(_to_float(data.get("f167")), 2),
                "market_cap": _to_float(data.get("f116")),
                "float_market_cap": _to_float(data.get("f117")),
                "market_cap_yi": _round((_to_float(data.get("f116")) or 0) / 1e8, 2),
                "float_cap_yi": _round((_to_float(data.get("f117")) or 0) / 1e8, 2),
                "industry": str(data.get("f127") or "") or None,
                "region": str(data.get("f128") or "") or None,
                "concepts": [part for part in str(data.get("f129") or "").split(",") if part],
                "industry_source": "东方财富个股快照",
            })
            profile["sources"].append("东方财富个股快照")
    except Exception as exc:
        profile["notes"].append(f"东方财富个股快照不可用：{str(exc)[:100]}")

    if profile["pb"] is None:
        try:
            snap = ds._cache_get("market_snapshot_v2", 600)
            if snap:
                match = next((item for item in snap.get("items", []) if item["symbol"] == display), None)
                if match:
                    profile.update({
                        "pb": match.get("pb"),
                        "pe_ttm": profile["pe_ttm"] or match.get("pe"),
                        "market_cap_yi": profile["market_cap_yi"] or match.get("market_cap_yi"),
                        "float_cap_yi": profile["float_cap_yi"] or match.get("float_cap_yi"),
                    })
                    profile["sources"].append("新浪全市场快照")
        except Exception:
            pass

    profile["notes"].append("PE 为腾讯 TTM 口径；PB 优先腾讯快照字段；行业/概念仅在东方财富快照可用时展示。")
    return profile
