"""行情获取模块测试（AkShare 全部 mock，不触网）。"""
from __future__ import annotations

import pandas as pd
import pytest

from app.market.provider import MarketDataProvider
from app.market.schemas import HistoryBar


def test_normalize_symbol():
    assert MarketDataProvider.normalize_symbol("1") == "000001"
    assert MarketDataProvider.normalize_symbol(" 600519 ") == "600519"
    assert MarketDataProvider.normalize_symbol("SZ000001") == "000001"
    with pytest.raises(ValueError):
        MarketDataProvider.normalize_symbol("ABC")
    with pytest.raises(ValueError):
        MarketDataProvider.normalize_symbol("1234567")


def test_history_mapping(monkeypatch, fake_daily_df):
    """中文列 -> 英文列映射与类型转换正确。"""
    provider = MarketDataProvider()
    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_hist", lambda **kwargs: fake_daily_df)

    df = provider.get_daily_history("000001")
    required = {"date", "open", "close", "high", "low", "volume", "amount", "pct_change"}
    assert required.issubset(set(df.columns))
    assert len(df) == 2

    bars = provider.to_history_response("000001", df)
    assert isinstance(bars[0], HistoryBar)
    assert bars[0].close == 10.2
    assert bars[1].date.isoformat() == "2026-09-07"
    assert bars[1].volume == 1200000


def test_history_empty(monkeypatch):
    """接口返回空时给出空 DataFrame。"""
    provider = MarketDataProvider()
    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_hist", lambda **kwargs: pd.DataFrame())
    df = provider.get_daily_history("000001")
    assert df.empty


def test_spot_quote_found(monkeypatch, fake_spot_df):
    provider = MarketDataProvider()
    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_spot_em", lambda: fake_spot_df)
    raw = provider.get_spot_quote("1")
    assert raw["名称"] == "平安银行"
    assert raw["最新价"] == 10.5


def test_spot_quote_not_found(monkeypatch, fake_spot_df):
    provider = MarketDataProvider()
    monkeypatch.setattr("app.market.provider.ak.stock_zh_a_spot_em", lambda: fake_spot_df)
    with pytest.raises(KeyError):
        provider.get_spot_quote("999999")


def test_individual_info(monkeypatch, fake_company_info_df):
    provider = MarketDataProvider()
    monkeypatch.setattr(
        "app.market.provider.ak.stock_individual_info_em",
        lambda **kwargs: fake_company_info_df,
    )
    info = provider.get_individual_info("000001")
    assert info["股票简称"] == "平安银行"
