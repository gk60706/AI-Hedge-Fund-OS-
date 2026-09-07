from __future__ import annotations

import pandas as pd
import pytest

from tools.market_tool import MarketDataError, _to_float, get_a_share_quote


def _fake_df(code: str = "300394") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "代码": code,
                "名称": "天孚通信",
                "最新价": 88.50,
                "涨跌幅": 2.35,
                "涨跌额": 2.04,
                "成交量": 123456,
                "成交额": 1200000000.0,
                "振幅": 3.50,
                "最高": 89.90,
                "最低": 86.00,
                "今开": 86.50,
                "昨收": 86.46,
                "换手率": 1.80,
                "市盈率-动态": 55.20,
                "市净率": 6.10,
                "总市值": 48000000000.0,
            }
        ]
    )


def test_get_a_share_quote_success(monkeypatch):
    monkeypatch.setattr("tools.market_tool.ak.stock_zh_a_spot_em", lambda: _fake_df())
    result = get_a_share_quote("300394")
    assert result["code"] == "300394"
    assert result["name"] == "天孚通信"
    assert result["latest_price"] == 88.5
    assert result["change_pct"] == 2.35
    assert result["pe_dynamic"] == 55.2
    assert result["source"] == "AkShare stock_zh_a_spot_em"


def test_get_a_share_quote_zero_padded_code(monkeypatch):
    monkeypatch.setattr("tools.market_tool.ak.stock_zh_a_spot_em", lambda: _fake_df())
    result = get_a_share_quote("300394")
    assert result["code"] == "300394"


def test_get_a_share_quote_invalid_code():
    with pytest.raises(ValueError):
        get_a_share_quote("abc")
    with pytest.raises(ValueError):
        get_a_share_quote("123")


def test_get_a_share_quote_not_found(monkeypatch):
    monkeypatch.setattr("tools.market_tool.ak.stock_zh_a_spot_em", lambda: _fake_df())
    with pytest.raises(MarketDataError):
        get_a_share_quote("999999")


def test_get_a_share_quote_empty_dataframe(monkeypatch):
    monkeypatch.setattr("tools.market_tool.ak.stock_zh_a_spot_em", lambda: pd.DataFrame())
    with pytest.raises(MarketDataError):
        get_a_share_quote("300394")


def test_get_a_share_quote_network_error(monkeypatch):
    def boom() -> pd.DataFrame:
        raise ConnectionError("network down")

    monkeypatch.setattr("tools.market_tool.ak.stock_zh_a_spot_em", boom)
    with pytest.raises(MarketDataError):
        get_a_share_quote("300394")


def test_to_float():
    assert _to_float(None) is None
    assert _to_float("12.5") == 12.5
    assert _to_float(88) == 88.0
    assert _to_float(float("nan")) is None
    assert _to_float("not-a-number") is None
