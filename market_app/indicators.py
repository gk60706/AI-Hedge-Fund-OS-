from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# TA-Lib compatible primitives
# ---------------------------------------------------------------------------

def _as_float(values: Any) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def ema_talib(values: Any, period: int) -> np.ndarray:
    """EMA with the same SMA seed convention as TA-Lib.

    TA-Lib emits its first EMA at index ``period - 1`` using the simple mean
    of the first ``period`` values, then applies the recursive EMA.
    """

    arr = _as_float(values)
    out = np.full(arr.shape, np.nan, dtype=np.float64)
    if period <= 0 or arr.size < period:
        return out

    # Indicators such as MACD/STOCH feed arrays with leading NaNs. TA-Lib
    # starts the EMA at the first window that is fully populated.
    seed_end = None
    for start in range(arr.size - period + 1):
        window = arr[start : start + period]
        if np.all(np.isfinite(window)):
            seed_end = start + period - 1
            seed = float(window.mean())
            break
    if seed_end is None:
        return out

    out[seed_end] = seed
    alpha = 2.0 / (period + 1.0)
    for i in range(seed_end + 1, arr.size):
        value = arr[i]
        if not np.isfinite(value):
            continue
        out[i] = alpha * value + (1.0 - alpha) * out[i - 1]
    return out


def sma_talib(values: Any, period: int) -> np.ndarray:
    arr = _as_float(values)
    out = np.full(arr.shape, np.nan, dtype=np.float64)
    if period <= 0 or arr.size < period:
        return out
    for i in range(period - 1, arr.size):
        window = arr[i - period + 1 : i + 1]
        if np.all(np.isfinite(window)):
            out[i] = window.mean()
    return out


def rolling_min(values: Any, period: int) -> np.ndarray:
    return pd.Series(_as_float(values)).rolling(period, min_periods=period).min().to_numpy()


def rolling_max(values: Any, period: int) -> np.ndarray:
    return pd.Series(_as_float(values)).rolling(period, min_periods=period).max().to_numpy()


def macd_talib(close: Any, fast: int = 12, slow: int = 26, signal: int = 9):
    close_arr = _as_float(close)
    fast_ema = ema_talib(close_arr, fast)
    slow_ema = ema_talib(close_arr, slow)
    dif = fast_ema - slow_ema
    dea = ema_talib(dif, signal)
    hist = dif - dea
    return dif, dea, hist


def rsi_talib(close: Any, period: int = 14) -> np.ndarray:
    """Wilder RSI, matching TA-Lib's first-value convention."""

    close_arr = _as_float(close)
    out = np.full(close_arr.shape, np.nan, dtype=np.float64)
    if close_arr.size <= period:
        return out
    delta = np.diff(close_arr, prepend=close_arr[0])
    gain = np.maximum(delta, 0.0)
    loss = np.maximum(-delta, 0.0)
    avg_gain = float(np.mean(gain[1 : period + 1]))
    avg_loss = float(np.mean(loss[1 : period + 1]))
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, close_arr.size):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def stoch_talib(high: Any, low: Any, close: Any, fastk: int = 9, slowk: int = 5, slowd: int = 5):
    high_arr = _as_float(high)
    low_arr = _as_float(low)
    close_arr = _as_float(close)
    highest = rolling_max(high_arr, fastk)
    lowest = rolling_min(low_arr, fastk)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw_k = 100.0 * (close_arr - lowest) / (highest - lowest)
    raw_k[~np.isfinite(raw_k)] = np.nan
    k = ema_talib(raw_k, slowk)
    d = ema_talib(k, slowd)
    j = 3.0 * k - 2.0 * d
    return k, d, j


def boll_talib(close: Any, period: int = 20, width: float = 2.0):
    series = pd.Series(_as_float(close))
    mid = series.rolling(period, min_periods=period).mean()
    std = series.rolling(period, min_periods=period).std(ddof=0)
    upper = mid + width * std
    lower = mid - width * std
    return upper.to_numpy(), mid.to_numpy(), lower.to_numpy()


def atr_talib(high: Any, low: Any, close: Any, period: int = 14) -> np.ndarray:
    high_arr = _as_float(high)
    low_arr = _as_float(low)
    close_arr = _as_float(close)
    n = close_arr.size
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= period:
        return out
    tr = np.full(n, np.nan, dtype=np.float64)
    tr[0] = high_arr[0] - low_arr[0]
    for i in range(1, n):
        tr[i] = max(
            high_arr[i] - low_arr[i],
            abs(high_arr[i] - close_arr[i - 1]),
            abs(low_arr[i] - close_arr[i - 1]),
        )
    out[period] = float(np.mean(tr[1 : period + 1]))
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def supertrend(
    high: Any,
    low: Any,
    close: Any,
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Classic Supertrend (ATR bands + trailing stop).

    Returns ``(direction, line, final_upper, final_lower)``. ``direction`` is
    ``1`` for an uptrend, ``-1`` for a downtrend and ``0`` before the first
    valid ATR value. This is a clean-room implementation of the public
    algorithm, not a copy of the GPL Pine script.
    """

    high_arr = _as_float(high)
    low_arr = _as_float(low)
    close_arr = _as_float(close)
    n = close_arr.size
    direction = np.zeros(n, dtype=np.int8)
    line = np.full(n, np.nan, dtype=np.float64)
    final_upper = np.full(n, np.nan, dtype=np.float64)
    final_lower = np.full(n, np.nan, dtype=np.float64)
    if n == 0 or period <= 0:
        return direction, line, final_upper, final_lower

    atr = atr_talib(high_arr, low_arr, close_arr, period)
    hl2 = (high_arr + low_arr) / 2.0
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    for i in range(n):
        if not (np.isfinite(upper[i]) and np.isfinite(lower[i])):
            continue
        if i == 0 or not np.isfinite(final_upper[i - 1]):
            final_upper[i] = upper[i]
            final_lower[i] = lower[i]
            direction[i] = 1 if close_arr[i] >= hl2[i] else -1
            line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]
            continue

        if upper[i] < final_upper[i - 1] or close_arr[i - 1] > final_upper[i - 1]:
            final_upper[i] = upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        if lower[i] > final_lower[i - 1] or close_arr[i - 1] < final_lower[i - 1]:
            final_lower[i] = lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        previous = int(direction[i - 1])
        if previous == 1:
            direction[i] = -1 if close_arr[i] < final_lower[i] else 1
        elif previous == -1:
            direction[i] = 1 if close_arr[i] > final_upper[i] else -1
        else:
            direction[i] = 1 if close_arr[i] >= hl2[i] else -1

        line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

    return direction, line, final_upper, final_lower


# ---------------------------------------------------------------------------
# Full indicator table
# ---------------------------------------------------------------------------

def compute_indicators(
    df: pd.DataFrame,
    st_period: int = 10,
    st_multiplier: float = 3.0,
) -> pd.DataFrame:
    """Return a copy with the indicators used by the UI.

    Required input columns: date, open, high, low, close, volume.
    Amount is optional but recommended for provenance/显示.
    ``st_period`` / ``st_multiplier`` exist so the backtest can perturb the
    Supertrend parameters without forking the indicator code.
    """

    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"缺少字段: {', '.join(sorted(missing))}")

    data = df.copy()
    data["date"] = data["date"].astype(str)
    for column in ("open", "high", "low", "close", "volume", "amount"):
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    data = data.sort_values("date").reset_index(drop=True)
    if data.empty:
        return data

    close = data["close"].to_numpy(dtype=np.float64)
    high = data["high"].to_numpy(dtype=np.float64)
    low = data["low"].to_numpy(dtype=np.float64)
    volume = data["volume"].to_numpy(dtype=np.float64)

    for period in (5, 10, 20, 30, 60, 120, 200):
        data[f"ma{period}"] = sma_talib(close, period)

    dif, dea, hist = macd_talib(close)
    data["macd_dif"] = dif
    data["macd_dea"] = dea
    data["macd_hist"] = hist

    data["rsi14"] = rsi_talib(close, 14)
    data["rsi6"] = rsi_talib(close, 6)
    data["rsi12"] = rsi_talib(close, 12)
    data["rsi24"] = rsi_talib(close, 24)

    k, d, j = stoch_talib(high, low, close, fastk=9, slowk=5, slowd=5)
    data["kdj_k"] = k
    data["kdj_d"] = d
    data["kdj_j"] = j

    upper, mid, lower = boll_talib(close)
    data["boll_upper"] = upper
    data["boll_mid"] = mid
    data["boll_lower"] = lower

    data["atr14"] = atr_talib(high, low, close, 14)
    data["atr_pct"] = data["atr14"] / data["close"] * 100.0

    data["atr10"] = atr_talib(high, low, close, st_period)
    st_dir, st_line, st_upper, st_lower = supertrend(
        high, low, close, period=st_period, multiplier=st_multiplier
    )
    data["st_period"] = int(st_period)
    data["st_multiplier"] = float(st_multiplier)
    data["st_dir"] = st_dir
    data["st_line"] = st_line
    data["st_upper"] = st_upper
    data["st_lower"] = st_lower

    data["vol_ma5"] = sma_talib(volume, 5)
    data["vol_ma10"] = sma_talib(volume, 10)
    data["vol_ma20"] = sma_talib(volume, 20)
    data["vol_ratio_5"] = volume / data["vol_ma5"].to_numpy()
    data["vol_ratio_20"] = volume / data["vol_ma20"].to_numpy()
    # 量比门要求分母不含当日，避免当天放量把自己的基准抬高。
    data["vol_ma20_prev"] = data["volume"].shift(1).rolling(20, min_periods=20).mean()
    data["vol_ratio_20_prev"] = volume / data["vol_ma20_prev"].to_numpy()

    data["pct_change"] = data["close"].pct_change() * 100.0
    for period in (5, 10, 20, 60, 120):
        data[f"ret{period}"] = (data["close"] / data["close"].shift(period) - 1.0) * 100.0

    for period in (20, 60, 120):
        data[f"high{period}"] = rolling_max(high, period)
        data[f"low{period}"] = rolling_min(low, period)

    return data


# ---------------------------------------------------------------------------
# Snapshot / trend classification
# ---------------------------------------------------------------------------

def _f(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return round(number, digits)


def _last_number(df: pd.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    return _f(df[column].iloc[-1])


def _macd_cross_recent(df: pd.DataFrame, lookback: int = 5) -> bool:
    if "macd_hist" not in df.columns or len(df) < lookback + 1:
        return False
    recent = df["macd_hist"].tail(lookback + 1).to_numpy(dtype=float)
    for index in range(1, len(recent)):
        if np.isfinite(recent[index - 1]) and np.isfinite(recent[index]):
            if recent[index - 1] <= 0 < recent[index]:
                return True
    return False


def build_snapshot(df: pd.DataFrame, index_return_20: float | None = None) -> dict[str, Any]:
    if df.empty:
        return {"ok": False, "error": "没有可用的行情数据"}

    last = df.iloc[-1]
    close = _f(last.get("close"))
    pct = _f(last.get("pct_change"))
    ma5 = _last_number(df, "ma5")
    ma10 = _last_number(df, "ma10")
    ma20 = _last_number(df, "ma20")
    ma60 = _last_number(df, "ma60")
    ma120 = _last_number(df, "ma120")
    dif = _last_number(df, "macd_dif")
    dea = _last_number(df, "macd_dea")
    hist = _last_number(df, "macd_hist")
    rsi = _last_number(df, "rsi14")
    kdj_k = _last_number(df, "kdj_k")
    kdj_d = _last_number(df, "kdj_d")
    boll_upper = _last_number(df, "boll_upper")
    boll_mid = _last_number(df, "boll_mid")
    boll_lower = _last_number(df, "boll_lower")
    atr = _last_number(df, "atr14")
    atr_pct = _last_number(df, "atr_pct")
    vol_ratio_5 = _last_number(df, "vol_ratio_5")
    vol_ratio_20 = _last_number(df, "vol_ratio_20")
    high20 = _last_number(df, "high20")
    low20 = _last_number(df, "low20")
    high60 = _last_number(df, "high60")
    low60 = _last_number(df, "low60")
    high120 = _last_number(df, "high120")
    low120 = _last_number(df, "low120")
    ret20 = _last_number(df, "ret20")
    ret60 = _last_number(df, "ret60")
    ret120 = _last_number(df, "ret120")

    score = 0.0
    max_score = 100.0
    reasons: list[str] = []
    risks: list[str] = []

    # 1) Moving-average structure, 25
    ma_score = 0.0
    if close is not None and ma20 is not None and close > ma20:
        ma_score += 8
        reasons.append("收盘价站上 MA20")
    if ma20 is not None and ma60 is not None and ma20 > ma60:
        ma_score += 8
        reasons.append("MA20 高于 MA60，中期结构向上")
    if ma5 is not None and ma10 is not None and ma20 is not None and ma5 > ma10 > ma20:
        ma_score += 9
        reasons.append("MA5 > MA10 > MA20，短期多头排列")
    score += ma_score

    # 2) MACD, 20
    macd_score = 0.0
    if dif is not None and dea is not None and dif > dea:
        macd_score += 10
        reasons.append("MACD 的 DIF 位于 DEA 上方")
    if hist is not None and hist > 0:
        macd_score += 5
        reasons.append("MACD 柱线为正")
    if _macd_cross_recent(df, 5):
        macd_score += 5
        reasons.append("最近 5 个交易日出现 MACD 金叉")
    score += macd_score

    # 3) RSI, 15
    rsi_score = 0.0
    if rsi is not None:
        if 50 <= rsi <= 70:
            rsi_score = 15
            reasons.append("RSI 处于 50–70 的强势区间")
        elif 40 <= rsi < 50:
            rsi_score = 8
            reasons.append("RSI 处于 40–50 的中性偏强区间")
        elif 70 < rsi <= 78:
            rsi_score = 5
            reasons.append("RSI 高于 70，强度在但短线偏热")
            risks.append("RSI 已进入偏热区，追高需谨慎")
        elif rsi < 40:
            rsi_score = 2
            risks.append("RSI 低于 40，动能偏弱")
        else:
            rsi_score = 0
            risks.append("RSI 高于 78，短线过热风险上升")
    score += rsi_score

    # 4) Volume, 15
    volume_score = 0.0
    if vol_ratio_5 is not None:
        if vol_ratio_5 >= 1.2 and (pct or 0) > 0:
            volume_score = 15
            reasons.append(f"成交量为 5 日均量的 {vol_ratio_5:.2f} 倍，价涨量增")
        elif vol_ratio_5 >= 1.0:
            volume_score = 8
            reasons.append(f"成交量为 5 日均量的 {vol_ratio_5:.2f} 倍")
        else:
            volume_score = 3
            risks.append(f"成交量只有 5 日均量的 {vol_ratio_5:.2f} 倍，上攻量能不足")
    score += volume_score

    # 5) Price position in 20-day range, 15
    position_score = 0.0
    if close is not None and high20 is not None and low20 is not None and high20 > low20:
        position = (close - low20) / (high20 - low20)
        if position >= 0.95:
            position_score = 15
            reasons.append("价格位于 20 日区间上沿")
        elif position >= 0.7:
            position_score = 10
            reasons.append("价格位于 20 日区间偏上位置")
        elif position >= 0.4:
            position_score = 6
        else:
            position_score = 2
            risks.append("价格位于 20 日区间下沿")
    score += position_score

    # 6) Relative strength vs index, 10
    relative_score = 5.0
    if ret20 is not None and index_return_20 is not None:
        excess = ret20 - index_return_20
        if excess >= 8:
            relative_score = 10
            reasons.append(f"20 日跑赢上证指数 {excess:.1f} 个百分点")
        elif excess >= 0:
            relative_score = 7
            reasons.append(f"20 日略跑赢上证指数 {excess:.1f} 个百分点")
        else:
            relative_score = 2
            risks.append(f"20 日跑输上证指数 {abs(excess):.1f} 个百分点")
    score += relative_score

    score = round(max(0.0, min(score, max_score)), 1)
    if score >= 80:
        label = "强势上升"
        tone = "strong-up"
    elif score >= 65:
        label = "上升趋势"
        tone = "up"
    elif score >= 45:
        label = "震荡偏强"
        tone = "neutral-up"
    elif score >= 30:
        label = "震荡偏弱"
        tone = "neutral-down"
    else:
        label = "下降趋势"
        tone = "down"

    valid_fields = [
        ma5, ma10, ma20, ma60, dif, dea, hist, rsi, atr,
        high20, low20, ret20,
    ]
    confidence = round(sum(value is not None for value in valid_fields) / len(valid_fields), 2)

    # Key levels
    supports = [value for value in (ma20, ma60, low20, low60) if value is not None and close is not None and value <= close]
    resistances = [value for value in (high20, high60, high120) if value is not None and close is not None and value >= close]
    nearest_support = max(supports) if supports else None
    nearest_resistance = min(resistances) if resistances else None
    stop_atr = round(close - 2.0 * atr, 2) if close is not None and atr is not None else None

    return {
        "ok": True,
        "as_of": str(last.get("date")),
        "close": close,
        "change_pct": pct,
        "trend": {
            "score": score,
            "label": label,
            "tone": tone,
            "confidence": confidence,
            "reasons": reasons[:6],
            "risks": risks[:5],
            "components": {
                "ma": round(ma_score, 1),
                "macd": round(macd_score, 1),
                "rsi": round(rsi_score, 1),
                "volume": round(volume_score, 1),
                "position": round(position_score, 1),
                "relative": round(relative_score, 1),
            },
            "disclaimer": "评分只描述当前技术状态，不构成涨跌预测或投资建议。",
        },
        "moving_averages": {
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60, "ma120": ma120,
        },
        "macd": {"dif": dif, "dea": dea, "hist": hist},
        "rsi": {"rsi6": _last_number(df, "rsi6"), "rsi14": rsi, "rsi24": _last_number(df, "rsi24")},
        "kdj": {"k": kdj_k, "d": kdj_d, "j": _last_number(df, "kdj_j")},
        "boll": {"upper": boll_upper, "mid": boll_mid, "lower": boll_lower},
        "atr": {"value": atr, "pct": atr_pct},
        "volume": {
            "ratio_5": vol_ratio_5,
            "ratio_20": vol_ratio_20,
            "ma5": _last_number(df, "vol_ma5"),
            "ma20": _last_number(df, "vol_ma20"),
        },
        "range": {
            "high20": high20, "low20": low20,
            "high60": high60, "low60": low60,
            "high120": high120, "low120": low120,
        },
        "returns": {"ret5": _last_number(df, "ret5"), "ret20": ret20, "ret60": ret60, "ret120": ret120},
        "levels": {
            "support": nearest_support,
            "resistance": nearest_resistance,
            "atr_stop": stop_atr,
            "distance_to_support_pct": round((close - nearest_support) / close * 100, 2) if close and nearest_support else None,
            "distance_to_resistance_pct": round((nearest_resistance - close) / close * 100, 2) if close and nearest_resistance else None,
        },
        "index_return_20": _f(index_return_20),
    }


def series_payload(df: pd.DataFrame, limit: int = 360) -> dict[str, Any]:
    """Serialize the chart series as JSON-safe lists."""

    subset = df.tail(limit).copy()
    columns = [
        "date", "open", "high", "low", "close", "volume", "amount", "pct_change",
        "ma5", "ma10", "ma20", "ma60", "ma120",
        "boll_upper", "boll_mid", "boll_lower",
        "vwap20", "st_line", "st_upper", "st_lower",
        "macd_dif", "macd_dea", "macd_hist",
        "rsi14", "kdj_k", "kdj_d",
        "vol_ma5", "vol_ma20",
    ]
    result: dict[str, list[Any]] = {}
    for column in columns:
        if column not in subset.columns:
            result[column] = []
            continue
        values = []
        for value in subset[column].tolist():
            if isinstance(value, (np.floating, float)):
                values.append(_f(value, 4))
            elif isinstance(value, (np.integer, int)):
                values.append(int(value))
            else:
                values.append(value)
        result[column] = values
    return result
