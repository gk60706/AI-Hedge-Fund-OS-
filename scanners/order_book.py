"""V0.3 五档盘口接口：新浪行情（GBK，逗号分隔）。

字段索引（新浪 A 股五档）：
 0 名称, 1 今开, 2 昨收, 3 现价, 4 最高, 5 最低, 6 买一价, 7 卖一价,
 8 成交量(股), 9 成交额(元), 10 买一量, 11 买一价, 12 买二量, 13 买二价,
 14 买三量, 15 买三价, 16 买四量, 17 买四价, 18 买五量, 19 买五价,
 20 卖一量, 21 卖一价, 22 卖二量, 23 卖二价, 24 卖三量, 25 卖三价,
 26 卖四量, 27 卖四价, 28 卖五量, 29 卖五价, ...
"""
from __future__ import annotations

import urllib.request

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.sina.com.cn/",
}


def _market_prefix(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith(("4", "8")):
        return "bj"
    return "sz"


def get_order_book(code: str) -> dict:
    """新浪五档盘口。"""
    market = _market_prefix(code)
    url = f"http://hq.sinajs.cn/list={market}{code}"
    req = urllib.request.Request(url, headers=_HEADERS)
    data = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
    values = data.split('"')[1].split(",")
    return {
        "buy1_price": float(values[11]),
        "buy1_volume": int(values[10]),
        "sell1_price": float(values[21]),
        "sell1_volume": int(values[20]),
        "buy5_volume": sum(
            int(values[i]) for i in (10, 12, 14, 16, 18)
        ),
        "sell5_volume": sum(
            int(values[i]) for i in (20, 22, 24, 26, 28)
        ),
    }
