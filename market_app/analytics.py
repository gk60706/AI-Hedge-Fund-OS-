from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import data_sources as ds
from .config import CORE_GATES_ONLY, SCREEN_CACHE_DIR
from .indicators import build_snapshot, compute_indicators, series_payload
from .signal_quality import attach_signal_quality, latest_signal_quality


CONDITION_LABELS = {
    "ma_bull": "均线多头排列",
    "above_ma20": "站上 MA20",
    "above_ma60": "站上 MA60",
    "macd_positive": "MACD 柱线为正",
    "macd_gold": "近 5 日 MACD 金叉",
    "rsi_50_75": "RSI 50–75",
    "volume_expand": "放量 1.2 倍",
    "near_high20": "接近 20 日高点",
    "breakout20": "突破 20 日高点",
    "ret20_positive": "20 日涨幅为正",
    "kdj_gold": "KDJ 金叉",
}

_screen_cache_lock = threading.RLock()
_tencent_cooldown_until = 0.0
_tencent_cooldown_reason = ""
_verify_lock = threading.RLock()
_verify_cache: dict[str, dict[str, Any]] = {}
_verify_pending: dict[str, Any] = {}
_verify_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="verify")


def _safe(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return round(number, digits)


def _check_cross(primary: pd.DataFrame, tencent: pd.DataFrame) -> dict[str, Any]:
    """比较 BaoStock 与腾讯最新一根 K 线的日期和收盘价。"""
    if primary.empty or tencent.empty:
        return {"ok": False, "message": "缺少交叉校验数据"}
    primary_date = str(primary["date"].iloc[-1])
    tencent_date = str(tencent["date"].iloc[-1])
    if primary_date != tencent_date:
        return {
            "ok": False,
            "message": f"日期不一致: BaoStock {primary_date} vs 腾讯 {tencent_date}",
            "primary_date": primary_date,
            "tencent_date": tencent_date,
        }
    primary_close = float(primary["close"].iloc[-1])
    tencent_close = float(tencent["close"].iloc[-1])
    diff_pct = abs(primary_close - tencent_close) / primary_close * 100.0
    return {
        "ok": diff_pct <= 0.5,
        "message": f"BaoStock {primary_close:.2f} / 腾讯 {tencent_close:.2f}，差异 {diff_pct:.4f}%",
        "primary_close": round(primary_close, 4),
        "tencent_close": round(tencent_close, 4),
        "diff_pct": round(diff_pct, 4),
    }


def _deep_baostock_check(symbol: str, period: str, primary: pd.DataFrame) -> dict[str, Any]:
    try:
        bao_frame, _ = ds.get_baostock_history(symbol, period, 320)
        return _check_cross(bao_frame, primary)
    except Exception as exc:
        return {"ok": False, "message": f"BaoStock 深度校验失败: {exc}"}


def _finish_verify(key: str, future: Any) -> None:
    try:
        result = future.result()
    except Exception as exc:
        result = {"ok": False, "message": f"BaoStock 深度校验失败: {exc}"}
    with _verify_lock:
        _verify_cache[key] = result
        _verify_pending.pop(key, None)


def _verify_with_baostock(symbol: str, period: str, primary: pd.DataFrame) -> dict[str, Any]:
    """后台做 BaoStock 交叉校验；最多同步等 2.5 秒，超时先返回。"""
    key = f"{symbol}|{period}"
    with _verify_lock:
        cached = _verify_cache.get(key)
        if cached is not None:
            return dict(cached)
        future = _verify_pending.get(key)
        if future is None:
            future = _verify_executor.submit(_deep_baostock_check, symbol, period, primary)
            _verify_pending[key] = future
            future.add_done_callback(lambda item: _finish_verify(key, item))
    try:
        result = future.result(timeout=2.5)
    except Exception:
        return {
            "ok": True,
            "skipped": True,
            "message": "BaoStock 深度校验未在 2.5 秒内返回，已在后台继续；本次以腾讯主源 + 实时快照校验为准",
        }
    with _verify_lock:
        _verify_cache[key] = result
    return dict(result)


def analyze_symbol(raw_symbol: str, period: str = "day", bars: int = 320, core_only: bool = CORE_GATES_ONLY) -> dict[str, Any]:
    resolved = ds.resolve_symbol(raw_symbol)
    if not resolved.get("ok"):
        return {"ok": False, "error": resolved.get("error", "未找到该股票")}

    symbol = resolved["symbol"]
    try:
        frame, provenance = ds.get_tencent_history(symbol, period, bars)
    except Exception as exc:
        frame, provenance = ds.get_history(symbol, period, bars)
        provenance["fallback"] = True
        provenance["fallback_reason"] = f"腾讯主源失败: {exc}"
    if frame.empty:
        return {"ok": False, "error": "历史行情为空"}
    name = resolved.get("name", symbol)
    frame = compute_indicators(frame)
    frame = attach_signal_quality(
        frame, symbol, name=name, cooldown_days=10, core_only=core_only
    )
    quality = latest_signal_quality(frame, cooldown_days=10)

    quote = ds.get_quote(symbol)
    index_return = None
    try:
        index_frame, _ = ds.get_tencent_history("000001.SH", period, max(120, bars))
        index_frame = compute_indicators(index_frame)
        index_return = _safe(index_frame["ret20"].iloc[-1])
    except Exception:
        pass

    snapshot = build_snapshot(frame, index_return_20=index_return)
    snapshot["symbol"] = symbol
    snapshot["name"] = name
    snapshot["period"] = period
    snapshot["signal_quality"] = quality

    checks: list[dict[str, Any]] = []
    if quote:
        quote_date = str(quote.get("time", "")).split(" ")[0]
        if quote_date == str(frame["date"].iloc[-1]):
            diff = abs(float(quote["price"]) - float(frame["close"].iloc[-1])) / float(frame["close"].iloc[-1]) * 100
            checks.append({
                "name": "收盘价 vs 腾讯实时快照",
                "ok": diff <= 0.5,
                "message": f"{float(frame['close'].iloc[-1]):.2f} vs {float(quote['price']):.2f}，差异 {diff:.4f}%",
            })
        else:
            checks.append({
                "name": "收盘价 vs 腾讯实时快照",
                "ok": True,
                "message": f"行情日期不同（{quote_date or '未知'} vs {frame['date'].iloc[-1]}），不做同日比较",
            })

    if provenance.get("source") == "BaoStock":
        try:
            tencent_frame, _ = ds.get_tencent_history(symbol, period, max(80, min(bars, 320)))
            cross = _check_cross(frame, tencent_frame)
            checks.append({"name": "BaoStock vs 腾讯 K 线", **cross})
        except Exception as exc:
            checks.append({"name": "BaoStock vs 腾讯 K 线", "ok": False, "message": f"交叉校验失败: {exc}"})
    else:
        checks.append({"name": "BaoStock 深度校验", **_verify_with_baostock(symbol, period, frame)})

    checks.append({
        "name": "数据时间戳",
        "ok": True,
        "message": f"K 线截至 {frame['date'].iloc[-1]}；抓取时间 {provenance.get('fetched_at')}（北京时间）",
    })

    return {
        "ok": True,
        "symbol": symbol,
        "name": name,
        "period": period,
        "quote": quote,
        "snapshot": snapshot,
        "series": series_payload(frame, limit=min(max(bars, 120), 360)),
        "provenance": provenance,
        "source_checks": checks,
    }


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------

def _screen_cache_path(symbol: str) -> Path:
    return SCREEN_CACHE_DIR / f"{symbol.replace('.', '_')}.csv"


def _load_screen_history(symbol: str) -> pd.DataFrame:
    global _tencent_cooldown_until, _tencent_cooldown_reason

    import time

    path = _screen_cache_path(symbol)
    cached_frame: pd.DataFrame | None = None
    if path.is_file():
        # 盘中 10 分钟，收盘后 6 小时；用文件年龄做粗略控制。
        age = time.time() - path.stat().st_mtime
        try:
            cached_frame = pd.read_csv(path)
            if cached_frame.empty:
                cached_frame = None
        except Exception:
            cached_frame = None
        if cached_frame is not None and age < 600 and time.time() >= _tencent_cooldown_until:
            return cached_frame

    with _screen_cache_lock:
        throttled = time.time() < _tencent_cooldown_until
        reason = _tencent_cooldown_reason
    if throttled and cached_frame is not None:
        cached_frame.attrs["stale"] = True
        cached_frame.attrs["stale_reason"] = reason or "腾讯主源限流，使用本地缓存"
        return cached_frame
    if throttled:
        try:
            frame, _ = ds.get_baostock_history(symbol, "day", 320)
            frame.attrs["fallback"] = True
            frame.attrs["fallback_reason"] = reason or "腾讯主源限流，改用 BaoStock"
            return frame
        except Exception as bao_exc:
            raise ds.DataFetchError(reason or f"腾讯主源限流，BaoStock 也失败: {bao_exc}") from bao_exc

    try:
        frame, _ = ds.get_tencent_history(symbol, "day", 320)
        with _screen_cache_lock:
            temp = path.with_suffix(".tmp")
            frame.to_csv(temp, index=False, encoding="utf-8")
            temp.replace(path)
        return frame
    except Exception as exc:
        message = str(exc)
        if "501" in message or "429" in message:
            # 腾讯 WAF/限流时主动熔断 15 分钟，避免 300 只票反复撞墙。
            with _screen_cache_lock:
                if time.time() >= _tencent_cooldown_until:
                    _tencent_cooldown_until = time.time() + 900
                    _tencent_cooldown_reason = f"腾讯主源限流（HTTP 501/429），15 分钟内使用本地缓存：{message}"
        if cached_frame is not None:
            cached_frame.attrs["stale"] = True
            cached_frame.attrs["stale_reason"] = f"腾讯主源失败，使用本地缓存：{message}"
            return cached_frame
        try:
            frame, _ = ds.get_baostock_history(symbol, "day", 320)
            frame.attrs["fallback"] = True
            frame.attrs["fallback_reason"] = f"腾讯主源失败，改用 BaoStock：{message}"
            return frame
        except Exception as bao_exc:
            raise ds.DataFetchError(f"腾讯与 BaoStock 均失败: {message}; {bao_exc}") from bao_exc


def _macd_cross_recent(frame: pd.DataFrame, lookback: int = 5) -> bool:
    if "macd_hist" not in frame.columns or len(frame) < lookback + 1:
        return False
    values = frame["macd_hist"].tail(lookback + 1).to_numpy(dtype=float)
    for i in range(1, len(values)):
        if np.isfinite(values[i - 1]) and np.isfinite(values[i]) and values[i - 1] <= 0 < values[i]:
            return True
    return False


def _kdj_cross_recent(frame: pd.DataFrame, lookback: int = 5) -> bool:
    if "kdj_k" not in frame.columns or "kdj_d" not in frame.columns:
        return False
    k = frame["kdj_k"].tail(lookback + 1).to_numpy(dtype=float)
    d = frame["kdj_d"].tail(lookback + 1).to_numpy(dtype=float)
    for i in range(1, len(k)):
        if np.all(np.isfinite([k[i - 1], k[i], d[i - 1], d[i]])) and k[i - 1] <= d[i - 1] and k[i] > d[i]:
            return True
    return False


def evaluate_conditions(frame: pd.DataFrame, conditions: list[str]) -> tuple[list[str], dict[str, Any]]:
    last = frame.iloc[-1]

    def val(name: str) -> float | None:
        return _safe(last.get(name))

    close = val("close")
    ma20 = val("ma20")
    ma60 = val("ma60")
    rsi = val("rsi14")
    vol_ratio = val("vol_ratio_5")
    high20 = val("high20")
    ret20 = val("ret20")
    macd_hist = val("macd_hist")

    hits: list[str] = []
    if close is not None and ma20 is not None and ma60 is not None and val("ma5") is not None and val("ma10") is not None:
        if val("ma5") > val("ma10") > ma20 > ma60:
            hits.append("ma_bull")
    if close is not None and ma20 is not None and close > ma20:
        hits.append("above_ma20")
    if close is not None and ma60 is not None and close > ma60:
        hits.append("above_ma60")
    if macd_hist is not None and macd_hist > 0:
        hits.append("macd_positive")
    if _macd_cross_recent(frame):
        hits.append("macd_gold")
    if rsi is not None and 50 <= rsi <= 75:
        hits.append("rsi_50_75")
    if vol_ratio is not None and vol_ratio >= 1.2:
        hits.append("volume_expand")
    if close is not None and high20 is not None and close >= high20 * 0.98:
        hits.append("near_high20")
    if close is not None and high20 is not None and close >= high20:
        hits.append("breakout20")
    if ret20 is not None and ret20 > 0:
        hits.append("ret20_positive")
    if _kdj_cross_recent(frame):
        hits.append("kdj_gold")

    matched = [item for item in conditions if item in hits]
    metrics = {
        "close": close,
        "change_pct": val("pct_change"),
        "rsi14": rsi,
        "macd_hist": macd_hist,
        "vol_ratio_5": vol_ratio,
        "ret20": ret20,
        "high20": high20,
        "ma20": ma20,
        "ma60": ma60,
        "kdj_k": val("kdj_k"),
        "kdj_d": val("kdj_d"),
    }
    return matched, metrics


def _evaluate_all(conditions: list[str], hit_count: int, match_mode: str, min_matches: int) -> bool:
    if not conditions:
        return True
    if match_mode == "any":
        return hit_count >= 1
    if match_mode == "at_least":
        return hit_count >= max(1, min_matches)
    return hit_count == len(conditions)


def screen_universe(
    symbols: list[dict[str, Any]],
    conditions: list[str],
    match_mode: str = "all",
    min_matches: int = 2,
    max_results: int = 100,
    quality_filter: bool = True,
    daily_top_k: int = 5,
    cooldown_days: int = 10,
    strict_gates: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    conditions = [item for item in conditions if item in CONDITION_LABELS]
    total = len(symbols)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    lock = threading.Lock()

    # 选股页与单票页必须使用同一套趋势评分口径（含相对上证 20 日强度）。
    index_return_20: float | None = None
    try:
        index_frame, _ = ds.get_tencent_history("000001.SH", "day", 320)
        index_frame = compute_indicators(index_frame)
        if not index_frame.empty:
            index_return_20 = _safe(index_frame["ret20"].iloc[-1])
    except Exception:
        index_return_20 = None

    def work(item: dict[str, Any]) -> dict[str, Any] | None:
        symbol = item["symbol"]
        name = item.get("name", symbol)
        frame = _load_screen_history(symbol)
        stale = bool(frame.attrs.get("stale"))
        fallback = bool(frame.attrs.get("fallback"))
        data_note = frame.attrs.get("stale_reason") or frame.attrs.get("fallback_reason") or ""
        frame = compute_indicators(frame)
        if frame.empty:
            raise ValueError("K 线为空")
        frame = attach_signal_quality(
            frame, symbol, name=name, cooldown_days=cooldown_days, core_only=not strict_gates
        )
        quality = latest_signal_quality(frame, cooldown_days=cooldown_days)
        snapshot = build_snapshot(frame, index_return_20=index_return_20)
        matched, metrics = evaluate_conditions(frame, conditions)
        if quality_filter and not quality.get("eligible"):
            return None
        if not _evaluate_all(conditions, len(matched), match_mode, min_matches):
            return None
        return {
            "symbol": symbol,
            "name": name,
            "score": snapshot["trend"]["score"],
            "label": snapshot["trend"]["label"],
            "tone": snapshot["trend"]["tone"],
            "matched": matched,
            "match_count": len(matched),
            "metrics": metrics,
            "quality": quality,
            "quality_score": quality.get("score", 0),
            "signal_status": quality.get("status", "不合格"),
            "fresh_signal": bool(quality.get("fresh_signal", False)),
            "stale": stale,
            "fallback": fallback,
            "data_note": data_note,
            "as_of": str(frame["date"].iloc[-1]),
            "source": (
                "本地缓存（腾讯主源失败）" if stale else
                "BaoStock 前复权（腾讯主源失败）" if fallback else
                "腾讯财经 K 线（前复权）"
            ),
        }

    completed = 0
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="screen") as executor:
        futures = {executor.submit(work, item): item for item in symbols}
        for future in as_completed(futures):
            item = futures[future]
            completed += 1
            try:
                value = future.result()
                if value:
                    with lock:
                        results.append(value)
            except Exception as exc:
                with lock:
                    errors.append({"symbol": item["symbol"], "error": str(exc)[:160]})
            if progress and (completed % 5 == 0 or completed == total):
                progress(completed, total, item["symbol"])

    results.sort(
        key=lambda item: (
            bool(item.get("fresh_signal")),
            float(item.get("quality_score") or 0),
            item["match_count"],
            item["score"],
        ),
        reverse=True,
    )
    eligible_total = len(results)
    fresh_total = sum(1 for item in results if item.get("fresh_signal"))
    stale_total = sum(1 for item in results if item.get("stale"))
    fallback_total = sum(1 for item in results if item.get("fallback"))
    top_k = max(0, min(int(daily_top_k), 20))
    top_picks = results[:top_k] if top_k else []
    matched_total = len(results)
    results = results[: max(1, min(max_results, 200))]

    # 补名称：股票池已有名称；自定义池用腾讯快照补。
    missing_names = [item["symbol"] for item in results if not item.get("name") or item["name"] == item["symbol"]]
    if missing_names:
        try:
            for quote in ds.get_quotes(missing_names[:50]):
                for item in results:
                    if item["symbol"] == quote["symbol"]:
                        item["name"] = quote["name"]
        except Exception:
            pass

    return {
        "ok": True,
        "total": total,
        "evaluated": total - len(errors),
        "matched": matched_total,
        "eligible": eligible_total,
        "fresh": fresh_total,
        "stale": stale_total,
        "fallback": fallback_total,
        "displayed": len(results),
        "conditions": conditions,
        "match_mode": match_mode,
        "min_matches": min_matches,
        "quality_filter": bool(quality_filter),
        "strict_gates": bool(strict_gates),
        "core_gates_only": not strict_gates,
        "daily_top_k": top_k,
        "cooldown_days": int(cooldown_days),
        "top_picks": top_picks,
        "results": results,
        "errors": errors[:20],
        "error_count": len(errors),
        "as_of": ds.now_text(),
    }
