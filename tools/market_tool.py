from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests

# 数据源说明：
# AkShare 的 stock_zh_a_spot_em() 拉取全市场 A 股实时快照（约 60 页分页请求）。
# 东方财富 WAF 会对来自同一 IP 的突发请求做连接重置，全市场快照在该网络下极不稳定。
# 因此这里改用东财 push2 单股实时接口（AkShare 同一数据源、单次请求返回全部字段），
# 输出字段与 stock_zh_a_spot_em 完全一致。akshare 仍保留在 requirements 中供其他工具使用。
# WAF 按节点封禁：主域被重置时，自动轮换编号子域（实测 2.push2 / 33.push2 等可用）。
_QUOTE_HOSTS = (
    "push2.eastmoney.com",
    "1.push2.eastmoney.com",
    "2.push2.eastmoney.com",
    "7.push2.eastmoney.com",
    "33.push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "push2his.eastmoney.com",
)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_QUOTE_FIELDS = (
    "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f116,f162,f167,f168,f170"
)
# 东财 WAF 对本机突发请求会临时重置连接，退避重试后通常可恢复（实测 ~10-20s 解封）。
_RETRY_ATTEMPTS = 5
_RETRY_BACKOFF = 4.0  # 首次重试等待秒数，之后按 2 倍递增
_MAX_ATTEMPTS = _RETRY_ATTEMPTS

# 东财 WAF 对本机经代理的请求不稳定（直连 + 浏览器头最稳）。
# config 会自动继承系统代理供 OpenAI 使用，行情请求这里强制直连。
# 如需走代理，设置环境变量 EASTMONEY_USE_PROXY=1。
_DIRECT_PROXIES = (
    {"http": None, "https": None}
    if os.getenv("EASTMONEY_USE_PROXY", "0").strip().lower() in ("0", "false", "no")
    else None
)


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


def _fetch_quote_row(code: str) -> dict[str, Any] | None:
    """按主机池轮询单股实时行情；全部失败返回 None（供上层退避重试）。"""
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


def get_a_share_quote(code: str) -> dict[str, Any]:
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        raise ValueError("股票代码必须是 6 位数字，例如 300394")

    raw: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            raw = _fetch_quote_row(code)
        except Exception as exc:  # noqa: BLE001 - 网络层任意异常统一走重试
            last_error = exc
            raw = None
        if raw is not None:
            break
        if last_error is None:
            last_error = MarketDataError("获取行情失败：东方财富接口无返回或连接被重置")
        if attempt < _MAX_ATTEMPTS - 1:
            time.sleep(_RETRY_BACKOFF * (2**attempt))
    if raw is None:
        raise MarketDataError(f"获取行情失败: {last_error}") from last_error

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
        "source": "AkShare/eastmoney push2 single-stock",
    }
