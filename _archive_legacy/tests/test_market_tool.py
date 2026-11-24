from __future__ import annotations

import pytest

from tools.market_tool import (
    MarketDataError,
    _fetch_quote_row_sina,
    _fetch_quote_row_tencent,
    _map_sina,
    _map_tencent,
    _to_float,
    get_a_share_quote,
)


def _fake_eastmoney_raw(code: str = "300394") -> dict:
    """模拟东财 push2 单股接口返回的 data 字段。"""
    return {
        "f43": 88.50,   # 最新价
        "f44": 89.90,   # 最高
        "f45": 86.00,   # 最低
        "f46": 86.50,   # 今开
        "f47": 123456,  # 成交量(手)
        "f48": 1200000000.0,  # 成交额(元)
        "f50": 1.20,    # 量比
        "f57": code,    # 代码
        "f58": "天孚通信",  # 名称
        "f60": 86.46,   # 昨收
        "f116": 48000000000.0,  # 总市值(元)
        "f162": 55.20,  # 市盈率-动态
        "f167": 6.10,   # 市净率
        "f168": 1.80,   # 换手率
        "f170": 2.35,   # 涨跌幅
    }


def _fake_tencent_raw(code: str = "300394") -> dict:
    """模拟腾讯 qt.gtimg.cn 解析后的字段（真实抓取值）。"""
    return {
        "name": "天孚通信",
        "price": 267.00,
        "prev_close": 248.70,
        "open": 256.22,
        "volume_lots": 519294.0,
        "change_amount": 18.30,
        "change_pct": 7.36,
        "high": 268.87,
        "low": 254.40,
        "amount_wan": 1360654.0,
        "turnover_pct": 4.77,
        "pe_ttm": 125.41,
        "amplitude_pct": 5.82,
        "market_cap_yi": 2912.50,
        "pb": 46.61,
    }


def _fake_sina_raw(code: str = "300394") -> dict:
    """模拟新浪 hq.sinajs.cn 解析后的字段（真实抓取值）。"""
    return {
        "name": "天孚通信",
        "open": 256.22,
        "prev_close": 248.70,
        "price": 267.00,
        "high": 268.87,
        "low": 254.40,
        "volume_shares": 51929384.0,
        "amount_yuan": 13606540719.65,
    }


# ------------------------------------------------------------ 东财主源

def test_get_a_share_quote_success(monkeypatch):
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: _fake_eastmoney_raw())
    result = get_a_share_quote("300394")
    assert result["code"] == "300394"
    assert result["name"] == "天孚通信"
    assert result["latest_price"] == 88.5
    assert result["change_pct"] == 2.35
    assert result["change_amount"] == pytest.approx(2.04)  # 88.5 - 86.46
    assert result["amplitude_pct"] == pytest.approx(4.5108)
    assert result["pe_dynamic"] == 55.2
    assert result["pb"] == 6.1
    assert result["market_cap"] == 48000000000.0
    assert result["source"] == "AkShare/eastmoney push2 single-stock"


def test_get_a_share_quote_invalid_code():
    with pytest.raises(ValueError):
        get_a_share_quote("abc")
    with pytest.raises(ValueError):
        get_a_share_quote("123")


def test_get_a_share_quote_eastmoney_missing_fields(monkeypatch):
    raw = _fake_eastmoney_raw()
    raw["f43"] = "-"  # 停牌等情况
    raw["f60"] = "-"
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: raw)
    result = get_a_share_quote("300394")
    assert result["latest_price"] is None
    assert result["change_amount"] is None
    assert result["amplitude_pct"] is None


# ------------------------------------------------------------ 腾讯备源

def test_get_a_share_quote_tencent_fallback(monkeypatch):
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: None)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_tencent", lambda code: _fake_tencent_raw())
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_sina", lambda code: None)
    result = get_a_share_quote("300394")
    assert result["name"] == "天孚通信"
    assert result["latest_price"] == 267.0
    assert result["change_pct"] == 7.36
    assert result["amount_yuan"] == pytest.approx(13606540000.0)
    assert result["market_cap"] == pytest.approx(291250000000.0)
    assert result["pe_dynamic"] == 125.41
    assert result["source"] == "Tencent qt.gtimg.cn (fallback)"


# ------------------------------------------------------------ 新浪兜底

def test_get_a_share_quote_sina_fallback(monkeypatch):
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: None)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_tencent", lambda code: None)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_sina", lambda code: _fake_sina_raw())
    result = get_a_share_quote("300394")
    assert result["name"] == "天孚通信"
    assert result["latest_price"] == 267.0
    assert result["change_pct"] == pytest.approx(7.3583)
    assert result["volume_lots"] == pytest.approx(519293.84)
    assert result["turnover_pct"] is None
    assert result["pe_dynamic"] is None
    assert result["source"] == "Sina hq.sinajs.cn (fallback)"


# ------------------------------------------------------------ 全部失败

def test_get_a_share_quote_all_sources_fail(monkeypatch):
    monkeypatch.setattr("tools.market_tool._RETRY_BACKOFF", 0.0)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: None)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_tencent", lambda code: None)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_sina", lambda code: None)
    with pytest.raises(MarketDataError):
        get_a_share_quote("300394")


def test_get_a_share_quote_network_error(monkeypatch):
    def boom(code: str) -> dict:
        raise ConnectionError("network down")

    monkeypatch.setattr("tools.market_tool._RETRY_BACKOFF", 0.0)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", boom)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_tencent", boom)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row_sina", boom)
    with pytest.raises(MarketDataError):
        get_a_share_quote("300394")


# ------------------------------------------------------------ 解析函数

def test_parse_tencent_real_line(monkeypatch):
    """用真实抓取的腾讯返回行验证解析（2026-09-07 实抓，88 字段）。"""
    real_line = (
        'v_sz300394="51~天孚通信~300394~267.00~248.70~256.22~519294~281041~238252'
        "~267.00~921~266.99~8~266.97~1~266.92~2~266.91~3~267.01~106~267.02~7"
        "~267.03~8~267.04~1~267.05~16~~20260907160251~18.30~7.36~268.87~254.40~"
        "267.00/519294/13606540720~519294~1360654~4.77~125.41~~268.87~254.40~"
        '5.82~2906.00~2912.50~46.61~298.44~198.96~1.55~797~262.02~120.92~144.38'
        "~~~2.77~1360654.0720~605.5560~227~ A A~GP-A-CYB~84.75~1.52~0.32~37.17~"
        '30.61~374.50~100.31~7.01~19.71~-4.97~1088388049~1090825093~74.28~59.29'
        '~1088388049~~~101.40~0.09~~CNY~0~~266.90~112~";'
    )
    resp = type("R", (), {"encoding": "gbk", "text": real_line})()
    monkeypatch.setattr(
        "tools.market_tool.requests.get", lambda *a, **k: resp
    )
    raw = _fetch_quote_row_tencent("300394")
    assert raw is not None
    assert raw["name"] == "天孚通信"
    assert raw["price"] == 267.0
    assert raw["change_pct"] == 7.36
    assert raw["amount_wan"] == 1360654.0
    assert raw["market_cap_yi"] == 2912.5
    mapped = _map_tencent("300394", raw)
    assert mapped["market_cap"] == pytest.approx(291250000000.0)
    assert mapped["amount_yuan"] == pytest.approx(13606540000.0)


def test_parse_sina_real_line(monkeypatch):
    """用真实抓取的新浪返回行验证解析。"""
    real_line = (
        'var hq_str_sz300394="天孚通信,256.220,248.700,267.000,268.870,254.400,'
        "267.000,267.010,51929384,13606540719.650,92092,267.000,800,266.990,100,"
        "266.970,200,266.920,300,266.910,500,267.010,106,267.020,7,267.030,8,"
        '267.040,1,267.050,2026-09-07,15:58:51,00,"'
    )
    resp = type("R", (), {"encoding": "gbk", "text": real_line})()
    monkeypatch.setattr(
        "tools.market_tool.requests.get", lambda *a, **k: resp
    )
    raw = _fetch_quote_row_sina("300394")
    assert raw is not None
    assert raw["name"] == "天孚通信"
    assert raw["price"] == 267.0
    assert raw["volume_shares"] == 51929384.0
    mapped = _map_sina("300394", raw)
    assert mapped["change_pct"] == pytest.approx(7.3583)
    assert mapped["volume_lots"] == pytest.approx(519293.84)


def test_to_float():
    assert _to_float(None) is None
    assert _to_float("12.5") == 12.5
    assert _to_float(88) == 88.0
    assert _to_float(float("nan")) is None
    assert _to_float("-") is None
    assert _to_float("not-a-number") is None
