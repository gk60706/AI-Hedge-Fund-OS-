from __future__ import annotations

import numpy as np
import pandas as pd

from market_app.indicators import compute_indicators, supertrend
from market_app.signal_quality import attach_signal_quality, board_and_limit, latest_signal_quality


def _frame(close: np.ndarray, volume: np.ndarray | None = None) -> pd.DataFrame:
    n = len(close)
    dates = pd.date_range("2024-01-01", periods=n, freq="B").strftime("%Y-%m-%d")
    close = np.asarray(close, dtype=float)
    open_ = close - 0.2
    high = close + 0.5
    low = close - 0.6
    if volume is None:
        volume = np.full(n, 1_000_000.0)
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": np.nan,
        }
    )


def test_supertrend_uptrend_and_downtrend():
    up = np.linspace(10, 30, 80)
    down = np.linspace(30, 10, 80)
    frame_up = _frame(up)
    frame_down = _frame(down)
    for frame, expected in ((frame_up, 1), (frame_down, -1)):
        direction, line, _, _ = supertrend(frame["high"], frame["low"], frame["close"], 10, 3.0)
        assert direction[-1] == expected
        assert np.isfinite(line[-1])
        if expected == 1:
            assert line[-1] < frame["close"].iloc[-1]
        else:
            assert line[-1] > frame["close"].iloc[-1]


def test_vwap_proxy_matches_manual_calculation():
    frame = _frame(np.linspace(10, 20, 40), volume=np.linspace(1e6, 3e6, 40))
    data = compute_indicators(frame)
    data = attach_signal_quality(data, "600519.SH", "贵州茅台")
    row = data.iloc[-1]
    typical = (data["high"] + data["low"] + data["close"]) / 3.0
    expected = (typical * data["volume"]).tail(20).sum() / data["volume"].tail(20).sum()
    assert abs(float(row["vwap20"]) - float(expected)) < 1e-6
    assert row["vwap_source"] == "hlc3_proxy"


def test_limit_rules_for_main_board_and_st():
    assert board_and_limit("600519.SH", "贵州茅台") == ("主板", 0.10)
    assert board_and_limit("300750.SZ", "宁德时代") == ("创业板", 0.20)
    assert board_and_limit("688981.SH", "中芯国际") == ("科创板", 0.20)
    assert board_and_limit("830799.BJ", "艾融软件") == ("北交所", 0.30)
    assert board_and_limit("600000.SH", "*ST 浦发") == ("主板ST", 0.05)


def test_quality_panel_shape():
    frame = _frame(np.linspace(10, 20, 120), volume=np.linspace(1e6, 2e6, 120))
    data = compute_indicators(frame)
    data = attach_signal_quality(data, "600519.SH", "贵州茅台")
    quality = latest_signal_quality(data)
    assert quality["ok"] is True
    assert set(quality["gates"]) == {"daily_trend", "weekly_trend", "vwap", "volume", "body", "tradeable"}
    assert 0 <= quality["score"] <= 100
    assert quality["grade"] in {"A", "B", "C", "D"}
    assert quality["metrics"]["vwap_source"] == "hlc3_proxy"
