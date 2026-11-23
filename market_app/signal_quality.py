from __future__ import annotations

from datetime import datetime, time as dt_time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import numpy as np
import pandas as pd

from .indicators import supertrend


GATE_LABELS = {
    "daily_trend": "日线 Supertrend 多头",
    "weekly_trend": "周线 Supertrend 多头",
    "vwap": "收盘高于 20 日 VWAP 与当日均价",
    "volume": "量比 ≥ 1.2（前 20 日均量，不含当日）",
    "body": "实体占 K 线 ≥ 50%",
    "tradeable": "非涨停 / 非一字板",
}


def _round_price(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def board_and_limit(symbol: str, name: str = "") -> tuple[str, float]:
    """Return ``(board_label, limit_pct)`` for A-share / ETF symbols."""

    code = str(symbol).split(".")[0]
    upper_name = str(name).upper()
    if code.startswith(("300", "301")):
        return "创业板", 0.20
    if code.startswith(("688", "689")):
        return "科创板", 0.20
    if code.startswith(("8", "4", "920")):
        return "北交所", 0.30
    if code.startswith(("51", "56", "58", "159")):
        return "ETF", 0.10
    if "ST" in upper_name:
        return "主板ST", 0.05
    return "主板", 0.10


def _weekly_direction(data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Weekly Supertrend aligned without look-ahead.

    A weekly bar ending Friday is only exposed to daily rows on/after the next
    calendar day. This deliberately lags by one week on Friday itself: the
    backtest never sees a weekly close before it exists.
    """

    if len(data) < 30:
        empty = np.full(len(data), np.nan)
        return empty, empty.copy()

    dates = pd.to_datetime(data["date"], errors="coerce")
    if dates.isna().all():
        empty = np.full(len(data), np.nan)
        return empty, empty.copy()

    source = pd.DataFrame(
        {
            "open": pd.to_numeric(data["open"], errors="coerce").to_numpy(),
            "high": pd.to_numeric(data["high"], errors="coerce").to_numpy(),
            "low": pd.to_numeric(data["low"], errors="coerce").to_numpy(),
            "close": pd.to_numeric(data["close"], errors="coerce").to_numpy(),
            "volume": pd.to_numeric(data["volume"], errors="coerce").to_numpy(),
        },
        index=dates,
    )
    weekly = source.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    weekly = weekly.dropna(subset=["open", "high", "low", "close"])
    if len(weekly) < 12:
        empty = np.full(len(data), np.nan)
        return empty, empty.copy()

    direction, line, _, _ = supertrend(
        weekly["high"].to_numpy(),
        weekly["low"].to_numpy(),
        weekly["close"].to_numpy(),
        period=10,
        multiplier=3.0,
    )
    weekly = weekly.copy()
    weekly["w_st_dir"] = direction
    weekly["w_st_line"] = line
    # Friday close becomes usable the next day; daily rows in the same week
    # therefore read the previous completed week.
    weekly["available_date"] = weekly.index + pd.Timedelta(days=1)

    left = pd.DataFrame({"date_ts": dates}).sort_values("date_ts")
    right = weekly[["available_date", "w_st_dir", "w_st_line"]].sort_values("available_date")
    merged = pd.merge_asof(
        left,
        right,
        left_on="date_ts",
        right_on="available_date",
        direction="backward",
        allow_exact_matches=True,
    )
    return merged["w_st_dir"].to_numpy(dtype=float), merged["w_st_line"].to_numpy(dtype=float)


def _confirmed_bar(last_date: str) -> bool:
    """A daily bar is confirmed after 15:05 Beijing time, or on a later day."""

    try:
        from .data_sources import now_beijing
        now = now_beijing()
    except Exception:
        now = datetime.now()
    try:
        bar_date = pd.Timestamp(last_date).date()
    except Exception:
        return False
    if bar_date < now.date():
        return True
    return bar_date == now.date() and now.time() >= dt_time(15, 5)


def attach_signal_quality(
    frame: pd.DataFrame,
    symbol: str,
    name: str = "",
    cooldown_days: int = 10,
    volume_threshold: float = 1.2,
    body_threshold: float = 0.5,
    require_weekly: bool = True,
) -> pd.DataFrame:
    """Add the P0 daily signal-quality columns to an indicator frame."""

    if frame.empty:
        return frame

    data = frame.copy()
    data["date"] = data["date"].astype(str)
    for column in ("open", "high", "low", "close", "volume"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    data = data.sort_values("date").reset_index(drop=True)
    if data.empty:
        return data

    high = data["high"].to_numpy(dtype=float)
    low = data["low"].to_numpy(dtype=float)
    close = data["close"].to_numpy(dtype=float)
    open_ = data["open"].to_numpy(dtype=float)
    volume = data["volume"].to_numpy(dtype=float)
    typical = (high + low + close) / 3.0

    # 腾讯日线不返回成交额，用典型价×成交量估算 VWAP 并在 UI 明确标注；
    # BaoStock 有真实 amount 时优先用真实成交额。
    amount_usable = False
    if "amount" in data.columns:
        amount_values = pd.to_numeric(data["amount"], errors="coerce")
        valid_ratio = float(amount_values.notna().mean())
        amount_usable = valid_ratio >= 0.9 and bool((amount_values.dropna() > 0).all())
    if amount_usable:
        amount = pd.to_numeric(data["amount"], errors="coerce").to_numpy(dtype=float)
        vwap_source = "amount"
        vwap_note = "真实成交额口径"
    else:
        amount = typical * volume
        vwap_source = "hlc3_proxy"
        vwap_note = "腾讯日线无成交额，按典型价×成交量估算"

    amount_series = pd.Series(amount)
    volume_series = pd.Series(volume)
    rolling_amount = amount_series.rolling(20, min_periods=20).sum()
    rolling_volume = volume_series.rolling(20, min_periods=20).sum()
    vwap20 = (rolling_amount / rolling_volume).to_numpy(dtype=float)

    data["vwap20"] = vwap20
    data["vwap_source"] = vwap_source
    data["vwap20_dist_pct"] = (close / vwap20 - 1.0) * 100.0
    data["vwap20_slope_pct"] = (
        pd.Series(vwap20).pct_change(5, fill_method=None).to_numpy() * 100.0
    )
    data["day_vwap"] = typical
    data["close_above_day_vwap"] = close >= typical
    data["above_vwap20"] = close > vwap20

    daily_dir = data["st_dir"].to_numpy(dtype=float) if "st_dir" in data.columns else np.zeros(len(data))
    daily_line = data["st_line"].to_numpy(dtype=float) if "st_line" in data.columns else np.full(len(data), np.nan)
    weekly_dir, weekly_line = _weekly_direction(data)
    data["weekly_st_dir"] = weekly_dir
    data["weekly_st_line"] = weekly_line

    if "vol_ratio_20_prev" not in data.columns:
        data["vol_ma20_prev"] = data["volume"].shift(1).rolling(20, min_periods=20).mean()
        data["vol_ratio_20_prev"] = volume / data["vol_ma20_prev"].to_numpy()
    vol_ratio = data["vol_ratio_20_prev"].to_numpy(dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        body_ratio = np.abs(close - open_) / (high - low)
    body_ratio = np.where((high - low) <= 1e-9, np.where(close >= open_, 1.0, 0.0), body_ratio)
    data["body_ratio"] = body_ratio
    data["body_pct"] = body_ratio * 100.0

    board, limit_pct = board_and_limit(symbol, name)
    prev_close = data["close"].shift(1).to_numpy(dtype=float)
    limit_up = np.array([_round_price(p * (1.0 + limit_pct)) if np.isfinite(p) else np.nan for p in prev_close])
    limit_down = np.array([_round_price(p * (1.0 - limit_pct)) if np.isfinite(p) else np.nan for p in prev_close])
    at_limit_up = np.isfinite(limit_up) & (close >= limit_up - 0.02)
    one_word = (high - low) <= 1e-9
    tradeable = ~(at_limit_up | one_word)

    data["limit_pct"] = limit_pct
    data["limit_up_price"] = limit_up
    data["limit_down_price"] = limit_down
    data["at_limit_up"] = at_limit_up
    data["one_word"] = one_word
    data["tradeable"] = tradeable
    data["board"] = board

    gates = {
        "daily_trend": daily_dir == 1,
        "weekly_trend": (weekly_dir == 1) if require_weekly else np.ones(len(data), dtype=bool),
        "vwap": (close > vwap20) & (close >= typical),
        "volume": np.isfinite(vol_ratio) & (vol_ratio >= float(volume_threshold)),
        "body": np.isfinite(body_ratio) & (body_ratio >= float(body_threshold)),
        "tradeable": tradeable,
    }
    for key, values in gates.items():
        data[f"gate_{key}"] = values

    active_gates = ["daily_trend", "vwap", "volume", "body", "tradeable"]
    if require_weekly:
        active_gates.insert(1, "weekly_trend")
    gate_count = np.sum(
        np.column_stack([gates[key] for key in active_gates if key != "tradeable"]),
        axis=1,
    )
    data["gate_count"] = gate_count
    eligible = (gate_count == (5 if require_weekly else 4)) & gates["tradeable"]
    data["eligible"] = eligible

    fresh = np.zeros(len(data), dtype=bool)
    last_trigger = -10**9
    previous_eligible = False
    for i in range(len(data)):
        if bool(eligible[i]) and (i == 0 or not previous_eligible):
            if i - last_trigger >= max(1, int(cooldown_days)):
                fresh[i] = True
                last_trigger = i
        previous_eligible = bool(eligible[i])
    data["fresh_signal"] = fresh

    quality_score = np.zeros(len(data), dtype=float)
    quality_score += np.where(gates["daily_trend"], 20.0, 0.0)
    quality_score += np.where(gates["weekly_trend"], 15.0, 0.0)
    quality_score += np.where(
        np.isfinite(data["vwap20_dist_pct"].to_numpy(dtype=float)) & (data["vwap20_dist_pct"].to_numpy(dtype=float) > 0),
        np.clip(data["vwap20_dist_pct"].to_numpy(dtype=float) / 5.0, 0.0, 1.0) * 20.0,
        0.0,
    )
    quality_score += np.where(
        np.isfinite(vol_ratio),
        np.clip(vol_ratio / 2.0, 0.0, 1.0) * 20.0,
        0.0,
    )
    quality_score += np.where(
        np.isfinite(body_ratio),
        np.clip(body_ratio / 0.8, 0.0, 1.0) * 15.0,
        0.0,
    )
    quality_score += np.where(fresh, 10.0, 0.0)
    data["quality_score"] = np.round(np.clip(quality_score, 0.0, 100.0), 1)
    data["quality_grade"] = np.select(
        [data["quality_score"] >= 80, data["quality_score"] >= 65, data["quality_score"] >= 50],
        ["A", "B", "C"],
        default="D",
    )
    return data


def latest_signal_quality(data: pd.DataFrame, cooldown_days: int = 10) -> dict[str, Any]:
    """Turn the last row of a quality frame into a JSON-safe panel object."""

    if data.empty:
        return {"ok": False, "error": "没有信号质量数据"}

    last = data.iloc[-1]
    confirmed = _confirmed_bar(str(last.get("date", "")))
    eligible = bool(last.get("eligible", False))
    fresh = bool(last.get("fresh_signal", False)) and confirmed
    raw_fresh = bool(last.get("fresh_signal", False))
    gate_count = int(last.get("gate_count", 0) or 0)
    tradeable = bool(last.get("tradeable", False))

    def num(value: Any, digits: int = 4) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return round(number, digits) if np.isfinite(number) else None

    metrics = {
        "vwap20": num(last.get("vwap20"), 2),
        "vwap_source": str(last.get("vwap_source", "")),
        "vwap20_dist_pct": num(last.get("vwap20_dist_pct"), 2),
        "vwap20_slope_pct": num(last.get("vwap20_slope_pct"), 2),
        "day_vwap": num(last.get("day_vwap"), 2),
        "vol_ratio_20_prev": num(last.get("vol_ratio_20_prev"), 2),
        "vol_ma20_prev": num(last.get("vol_ma20_prev"), 2),
        "body_pct": num(last.get("body_pct"), 1),
        "st_dir": int(last.get("st_dir", 0) or 0),
        "st_line": num(last.get("st_line"), 2),
        "st_distance_pct": num((float(last.get("close")) / float(last.get("st_line")) - 1.0) * 100.0, 2)
        if num(last.get("st_line")) not in (None, 0)
        else None,
        "weekly_st_dir": int(last.get("weekly_st_dir")) if np.isfinite(float(last.get("weekly_st_dir", np.nan))) else None,
        "weekly_st_line": num(last.get("weekly_st_line"), 2),
        "atr10": num(last.get("atr10"), 2),
        "board": str(last.get("board", "")),
        "limit_pct": num(float(last.get("limit_pct", 0.1)) * 100.0, 1),
        "limit_up_price": num(last.get("limit_up_price"), 2),
        "limit_down_price": num(last.get("limit_down_price"), 2),
    }

    gates = {
        "daily_trend": bool(last.get("gate_daily_trend", False)),
        "weekly_trend": bool(last.get("gate_weekly_trend", False)),
        "vwap": bool(last.get("gate_vwap", False)),
        "volume": bool(last.get("gate_volume", False)),
        "body": bool(last.get("gate_body", False)),
        "tradeable": tradeable,
    }

    reasons: list[str] = []
    warnings: list[str] = []
    if gates["daily_trend"]:
        reasons.append("日线 Supertrend 为多头")
    else:
        warnings.append("日线 Supertrend 未转多")
    if gates["weekly_trend"]:
        reasons.append("上周确认的周线 Supertrend 为多头")
    else:
        warnings.append("周线 Supertrend 未确认多头")
    if gates["vwap"]:
        reasons.append(f"收盘高于 20 日 VWAP {metrics['vwap20_dist_pct'] or 0:.2f}%")
    else:
        warnings.append("收盘未同时站上 20 日 VWAP 与当日均价")
    if gates["volume"]:
        reasons.append(f"量比为前 20 日均量的 {metrics['vol_ratio_20_prev'] or 0:.2f} 倍")
    else:
        warnings.append("量能未达到前 20 日均量的 1.2 倍")
    if gates["body"]:
        reasons.append(f"实体占 K 线 {metrics['body_pct'] or 0:.1f}%")
    else:
        warnings.append("实体占 K 线不足 50%")
    if not tradeable:
        warnings.append("当日涨停或一字板，无法按收盘价追入")

    if not tradeable:
        status = "涨停/一字板"
    elif eligible and fresh:
        status = "新信号（收盘确认）" if confirmed else "盘中新信号（未确认）"
    elif eligible:
        status = "持续合格"
    elif gate_count >= 4:
        status = "接近合格"
    else:
        status = "不合格"

    if not confirmed and eligible:
        warnings.append("当日 K 线尚未收盘，信号为盘中 provisional")

    return {
        "ok": True,
        "as_of": str(last.get("date", "")),
        "confirmed": confirmed,
        "eligible": eligible,
        "fresh_signal": fresh,
        "raw_fresh": raw_fresh,
        "status": status,
        "score": num(last.get("quality_score"), 0),
        "grade": str(last.get("quality_grade", "D")),
        "gate_count": gate_count,
        "gates": gates,
        "metrics": metrics,
        "reasons": reasons,
        "warnings": warnings,
        "cooldown_days": int(cooldown_days),
        "vwap_note": "真实成交额口径" if metrics["vwap_source"] == "amount" else "腾讯日线无成交额，按典型价×成交量估算 VWAP",
        "disclaimer": "只做信号纪律与数据口径展示，不构成买卖建议或涨跌预测。",
    }
