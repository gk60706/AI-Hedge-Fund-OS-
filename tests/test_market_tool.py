from __future__ import annotations

import pytest

from tools.market_tool import MarketDataError, _to_float, get_a_share_quote


def _fake_raw(code: str = "300394") -> dict:
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


def test_get_a_share_quote_success(monkeypatch):
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: _fake_raw())
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


def test_get_a_share_quote_not_found(monkeypatch):
    monkeypatch.setattr("tools.market_tool._RETRY_BACKOFF", 0.0)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: None)
    with pytest.raises(MarketDataError):
        get_a_share_quote("999999")


def test_get_a_share_quote_network_error(monkeypatch):
    def boom(code: str) -> dict:
        raise ConnectionError("network down")

    monkeypatch.setattr("tools.market_tool._RETRY_BACKOFF", 0.0)
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", boom)
    with pytest.raises(MarketDataError):
        get_a_share_quote("300394")


def test_get_a_share_quote_missing_fields(monkeypatch):
    raw = _fake_raw()
    raw["f43"] = "-"  # 停牌等情况
    raw["f60"] = "-"
    monkeypatch.setattr("tools.market_tool._fetch_quote_row", lambda code: raw)
    result = get_a_share_quote("300394")
    assert result["latest_price"] is None
    assert result["change_amount"] is None
    assert result["amplitude_pct"] is None


def test_to_float():
    assert _to_float(None) is None
    assert _to_float("12.5") == 12.5
    assert _to_float(88) == 88.0
    assert _to_float(float("nan")) is None
    assert _to_float("-") is None
    assert _to_float("not-a-number") is None
