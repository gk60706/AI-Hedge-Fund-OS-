"""V0.3 扫描模块测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from agents.fund_agent import fund_agent
from agents.opportunity_agent import opportunity_score, rank_opportunity
from scanners.capital_flow import calculate_main_force_score
from scanners.order_book import get_order_book
from scanners.scanner import scan_market
from scanners.stock_pool import create_stock_pool, filter_liquidity, get_all_stock_pool


# ---------------------------------------------------------------- capital_flow

def test_main_force_score_strong_buy():
    book = {"buy5_volume": 300, "sell5_volume": 100}
    assert calculate_main_force_score(book, 2.5, 5.0) == 100


def test_main_force_score_clamped():
    book = {"buy5_volume": 10, "sell5_volume": 100}
    score = calculate_main_force_score(book, 0.5, 10.0)
    assert 0 <= score <= 100


def test_main_force_score_zero_sell():
    book = {"buy5_volume": 500, "sell5_volume": 0}
    assert calculate_main_force_score(book, 1.0, 5.0) >= 50


# ---------------------------------------------------------------- order_book

def test_order_book_parses_real_line(monkeypatch):
    # 新浪五档返回示例（真实格式）：名称,今开,昨收,现价,最高,最低,买一价,卖一价,成交量,成交额,
    # 买一量,买一价,买二量,买二价,买三量,买三价,买四量,买四价,买五量,买五价,
    # 卖一量,卖一价,卖二量,卖二价,卖三量,卖三价,卖四量,卖四价,卖五量,卖五价
    values = [
        "天孚通信", "256.22", "248.70", "267.00", "268.87", "254.40",
        "267.00", "267.01", "519294", "13606540720",
        "100", "267.00", "200", "266.99", "300", "266.98", "400", "266.97", "500", "266.96",
        "600", "267.01", "700", "267.02", "800", "267.03", "900", "267.04", "1000", "267.05",
    ]
    line = 'var hq_str_sz300394="' + ",".join(values) + '";'
    monkeypatch.setattr(
        "scanners.order_book.urllib.request.urlopen",
        lambda req, timeout: type(
            "R", (), {"read": lambda self: line.encode("gbk")}
        )(),
    )
    book = get_order_book("300394")
    assert book["buy1_price"] == 267.0
    assert book["buy1_volume"] == 100
    assert book["sell1_price"] == 267.01
    assert book["sell1_volume"] == 600
    assert book["buy5_volume"] == 1500  # 100+200+300+400+500
    assert book["sell5_volume"] == 4000  # 600+700+800+900+1000


# ---------------------------------------------------------------- fund_agent

def test_fund_agent(monkeypatch):
    monkeypatch.setattr(
        "agents.fund_agent.get_order_book",
        lambda code: {
            "buy1_price": 267.0, "buy1_volume": 100,
            "sell1_price": 267.01, "sell1_volume": 600,
            "buy5_volume": 1500, "sell5_volume": 4000,
        },
    )
    item = fund_agent({"代码": 300394, "名称": "天孚通信", "涨跌幅": 5.0})
    assert item["code"] == "300394"
    assert item["name"] == "天孚通信"
    assert 0 <= item["fund_score"] <= 100
    assert "order_book" in item


# ---------------------------------------------------------------- opportunity

def test_opportunity_score_and_rank():
    stocks = [
        {"code": "A", "fund_score": 90},
        {"code": "B", "fund_score": 60},
    ]
    ranked = rank_opportunity(stocks)
    assert ranked[0]["code"] == "A"
    assert ranked[0]["opportunity_score"] == pytest.approx(90 * 0.6 + 30)


def test_opportunity_score_formula():
    assert opportunity_score({"fund_score": 100}) == pytest.approx(90.0)


# ---------------------------------------------------------------- stock_pool

def test_filter_liquidity():
    df = pd.DataFrame(
        {"代码": ["000001", "000002"], "成交额": [1e8, 1e7]}
    )
    out = filter_liquidity(df, min_amount=5e7)
    assert list(out["代码"]) == ["000001"]


def test_create_stock_pool_empty_on_error(monkeypatch):
    def boom():
        raise RuntimeError("东财限流")
    monkeypatch.setattr("scanners.stock_pool.ak", None)
    pool = get_all_stock_pool()
    assert pool.empty


def test_scan_market_empty_pool(monkeypatch):
    monkeypatch.setattr(
        "scanners.scanner.create_stock_pool",
        lambda: pd.DataFrame(columns=["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]),
    )
    assert scan_market() == []
