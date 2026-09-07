from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests

# 数据源说明（多源容灾）：
# 1) 主源：东财 push2 单股实时接口（AkShare 的 stock_zh_a_spot_em 同源数据）。
#    AkShare 全市场快照约 60 页分页请求，东财 WAF 对同一 IP 的突发请求会临时重置连接，
#    因此改用单股接口 + 浏览器头 + 编号子域轮换 + 指数退避重试。
# 2) 备源：腾讯 qt.gtimg.cn 单股实时（字段完整，含 PE/PB/换手/振幅/市值，实测稳定）。
# 3) 兜底：新浪 hq.sinajs.cn 单股实时（基础行情字段，无 PE/PB/市值）。
# 输出字段与 stock_zh_a_spot_em 保持一致；缺字段填 None。akshare 保留在 requirements 中。
_QUOTE_HOSTS = (
    "push2.eastmoney.com",
    "1.push2.eastmoney.com",
    "2.push2.eastmoney.com",
    "7.push2.eastmoney.com",
    "33.push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "push2his.eastmoney.com",
)

_QUOTE_FIELDS = (
    "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f116,f162,f167,f168,f170"
)
# 东财 WAF 对本机突发请求会临时重置连接，退避重试后通常可恢复（实测 ~10-20s 解封）。
_RETRY_ATTEMPTS = 5
_RETRY_BACKOFF = 4.0  # 首次重试等待秒数，之后按 2 倍递增
_MAX_ATTEMPTS = _RETRY_ATTEMPTS

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 东财 WAF 对本机经代理的请求不稳定（直连 + 浏览器头最稳）。
# config 会自动继承系统代理供 OpenAI 使用，行情请求这里强制直连。
# 如需走代理，设置环境变量 EASTMONEY_USE_PROXY=1。
_DIRECT_PROXIES = (
    {"http": None, "https": None}
    if os.getenv("EASTMONEY_USE_PROXY", "0").strip().lower() in ("0", "false", "no")
    else None
)

_TENCENT_HEADERS = {
    "User-Agent": _BROWSER_HEADERS["User-Agent"],
    "Referer": "https://gu.qq.com/",
}

_SINA_HEADERS = {
    "User-Agent": _BROWSER_HEADERS["User-Agent"],
    "Referer": "https://finance.sina.com.cn/",
}

_SOURCE_LABELS = {
    "eastmoney": "AkShare/eastmoney push2 single-stock",
    "tencent": "Tencent qt.gtimg.cn (fallback)",
    "sina": "Sina hq.sinajs.cn (fallback)",
}


class MarketDataError(RuntimeError):
    pass


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str) and value.strip() == "-":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _secid(code: str) -> str:
    """A股代码转东财 secid：沪市(6/688)前缀 1.，深市/创业板/北交所前缀 0."""
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def _market_prefix(code: str) -> str:
    """腾讯/新浪市场前缀：沪市 sh、深市 sz、北交所 bj."""
    if code.startswith("6"):
        return "sh"
    if code.startswith(("4", "8")):
        return "bj"
    return "sz"


# ---------------------------------------------------------------- 数据源抓取

def _fetch_quote_row(code: str) -> dict[str, Any] | None:
    """主源：东财 push2 单股行情；按主机池轮询，全部失败返回 None."""
    params = {
        "secid": _secid(code),
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "invt": "2",
        "fltt": "2",
        "fields": _QUOTE_FIELDS,
    }
    for host in _QUOTE_HOSTS:
        try:
            resp = requests.get(
                f"https://{host}/api/qt/stock/get",
                params=params,
                headers=_BROWSER_HEADERS,
                timeout=15,
                proxies=_DIRECT_PROXIES,
            )
            resp.raise_for_status()
            data = resp.json().get("data")
            if data and data.get("f57"):
                return data
        except Exception:
            continue
    return None


def _fetch_quote_row_tencent(code: str) -> dict[str, Any] | None:
    """备源：腾讯 qt.gtimg.cn 单股行情；失败返回 None."""
    url = f"https://qt.gtimg.cn/q={_market_prefix(code)}{code}"
    try:
        resp = requests.get(
            url, headers=_TENCENT_HEADERS, timeout=10, proxies=_DIRECT_PROXIES
        )
        resp.encoding = "gbk"
        text = resp.text
        start = text.find('"')
        end = text.rfind('"')
        if start < 0 or end <= start:
            return None
        parts = text[start + 1 : end].split("~")
        if len(parts) < 47 or parts[2] != code:  # 需要覆盖到索引 46（市净率）
            return None
        return {
            "name": parts[1],
            "price": _to_float(parts[3]),
            "prev_close": _to_float(parts[4]),
            "open": _to_float(parts[5]),
            "volume_lots": _to_float(parts[6]),
            "change_amount": _to_float(parts[31]),
            "change_pct": _to_float(parts[32]),
            "high": _to_float(parts[33]),
            "low": _to_float(parts[34]),
            "amount_wan": _to_float(parts[37]),
            "turnover_pct": _to_float(parts[38]),
            "pe_ttm": _to_float(parts[39]),
            "amplitude_pct": _to_float(parts[43]),
            "market_cap_yi": _to_float(parts[45]),
            "pb": _to_float(parts[46]),
        }
    except Exception:
        return None


def _fetch_quote_row_sina(code: str) -> dict[str, Any] | None:
    """兜底：新浪 hq.sinajs.cn 单股行情；失败返回 None."""
    url = f"https://hq.sinajs.cn/list={_market_prefix(code)}{code}"
    try:
        resp = requests.get(
            url, headers=_SINA_HEADERS, timeout=10, proxies=_DIRECT_PROXIES
        )
        resp.encoding = "gbk"
        text = resp.text
        start = text.find('"')
        end = text.rfind('"')
        if start < 0 or end <= start:
            return None
        parts = text[start + 1 : end].split(",")
        if len(parts) < 10 or not parts[0]:
            return None
        return {
            "name": parts[0],
            "open": _to_float(parts[1]),
            "prev_close": _to_float(parts[2]),
            "price": _to_float(parts[3]),
            "high": _to_float(parts[4]),
            "low": _to_float(parts[5]),
            "volume_shares": _to_float(parts[8]),
            "amount_yuan": _to_float(parts[9]),
        }
    except Exception:
        return None


def _fetch_quote_any(code: str) -> tuple[dict[str, Any] | None, str | None]:
    """按 东财→腾讯→新浪 依次尝试；返回 (原始行情行, 数据源标识)。"""
    fetchers = (
        ("eastmoney", _fetch_quote_row),
        ("tencent", _fetch_quote_row_tencent),
        ("sina", _fetch_quote_row_sina),
    )
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        for source, fetcher in fetchers:
            try:
                raw = fetcher(code)
            except Exception as exc:  # noqa: BLE001 - 网络层任意异常统一走下一源
                last_error = exc
                raw = None
            if raw is not None:
                return raw, source
        if last_error is None:
            last_error = MarketDataError("获取行情失败：各数据源均无返回或连接被重置")
        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_RETRY_BACKOFF * (2**attempt))
    return None, None


# ---------------------------------------------------------------- 字段映射

def _map_eastmoney(code: str, raw: dict[str, Any]) -> dict[str, Any]:
    def f(name: str) -> Any:
        value = raw.get(name)
        return None if value in (None, "-") else value

    prev_close = _to_float(f("f60"))
    latest = _to_float(f("f43"))
    high = _to_float(f("f44"))
    low = _to_float(f("f45"))

    change_amount: float | None = None
    if latest is not None and prev_close is not None:
        change_amount = round(latest - prev_close, 4)

    amplitude_pct: float | None = None
    if high is not None and low is not None and prev_close:
        amplitude_pct = round((high - low) / prev_close * 100, 4)

    return {
        "code": code,
        "name": f("f58"),
        "latest_price": latest,
        "change_pct": _to_float(f("f170")),
        "change_amount": change_amount,
        "volume_lots": _to_float(f("f47")),
        "amount_yuan": _to_float(f("f48")),
        "amplitude_pct": amplitude_pct,
        "high": high,
        "low": low,
        "open": _to_float(f("f46")),
        "prev_close": prev_close,
        "turnover_pct": _to_float(f("f168")),
        "pe_dynamic": _to_float(f("f162")),
        "pb": _to_float(f("f167")),
        "market_cap": _to_float(f("f116")),
    }


def _map_tencent(code: str, raw: dict[str, Any]) -> dict[str, Any]:
    amount_yuan: float | None = None
    if raw.get("amount_wan") is not None:
        amount_yuan = round(raw["amount_wan"] * 10000, 2)
    market_cap: float | None = None
    if raw.get("market_cap_yi") is not None:
        market_cap = round(raw["market_cap_yi"] * 1e8, 2)
    return {
        "code": code,
        "name": raw.get("name"),
        "latest_price": raw.get("price"),
        "change_pct": raw.get("change_pct"),
        "change_amount": raw.get("change_amount"),
        "volume_lots": raw.get("volume_lots"),
        "amount_yuan": amount_yuan,
        "amplitude_pct": raw.get("amplitude_pct"),
        "high": raw.get("high"),
        "low": raw.get("low"),
        "open": raw.get("open"),
        "prev_close": raw.get("prev_close"),
        "turnover_pct": raw.get("turnover_pct"),
        "pe_dynamic": raw.get("pe_ttm"),
        "pb": raw.get("pb"),
        "market_cap": market_cap,
    }


def _map_sina(code: str, raw: dict[str, Any]) -> dict[str, Any]:
    latest = raw.get("price")
    prev_close = raw.get("prev_close")
    high = raw.get("high")
    low = raw.get("low")

    change_amount: float | None = None
    if latest is not None and prev_close is not None:
        change_amount = round(latest - prev_close, 4)
    change_pct: float | None = None
    if latest is not None and prev_close:
        change_pct = round((latest - prev_close) / prev_close * 100, 4)
    amplitude_pct: float | None = None
    if high is not None and low is not None and prev_close:
        amplitude_pct = round((high - low) / prev_close * 100, 4)
    volume_lots: float | None = None
    if raw.get("volume_shares") is not None:
        volume_lots = round(raw["volume_shares"] / 100, 2)

    return {
        "code": code,
        "name": raw.get("name"),
        "latest_price": latest,
        "change_pct": change_pct,
        "change_amount": change_amount,
        "volume_lots": volume_lots,
        "amount_yuan": raw.get("amount_yuan"),
        "amplitude_pct": amplitude_pct,
        "high": high,
        "low": low,
        "open": raw.get("open"),
        "prev_close": prev_close,
        "turnover_pct": None,
        "pe_dynamic": None,
        "pb": None,
        "market_cap": None,
    }


_MAPPERS = {
    "eastmoney": _map_eastmoney,
    "tencent": _map_tencent,
    "sina": _map_sina,
}


# ---------------------------------------------------------------- 对外接口

def get_a_share_quote(code: str) -> dict[str, Any]:
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        raise ValueError("股票代码必须是 6 位数字，例如 300394")

    raw, source = _fetch_quote_any(code)
    if raw is None or source is None:
        raise MarketDataError("获取行情失败：各数据源均不可用，请稍后重试")
    result = _MAPPERS[source](code, raw)
    result["source"] = _SOURCE_LABELS[source]
    return result
