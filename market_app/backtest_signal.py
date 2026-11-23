from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import data_sources as ds
from .indicators import compute_indicators
from .signal_quality import attach_signal_quality


def _fresh(raw: np.ndarray, cooldown: int = 10) -> np.ndarray:
    out = np.zeros(len(raw), dtype=bool)
    last = -10**9
    previous = False
    for i, value in enumerate(raw):
        if bool(value) and (i == 0 or not previous) and i - last >= cooldown:
            out[i] = True
            last = i
        previous = bool(value)
    return out


def _stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "trades": 0,
            "win_rate": None,
            "avg_return": None,
            "median_return": None,
            "profit_factor": None,
            "avg_excess": None,
            "t_excess": None,
            "max_drawdown": None,
        }
    # Thread completion order is nondeterministic; a drawdown path must use a
    # stable chronological order or the same run can report different numbers.
    trades = sorted(trades, key=lambda item: (item["exit_date"], item["entry_date"], item["symbol"]))
    returns = np.array([item["return_pct"] for item in trades], dtype=float)
    returns = returns[np.isfinite(returns)]
    excess = np.array([item["excess_pct"] for item in trades if item.get("excess_pct") is not None], dtype=float)
    wins = returns > 0
    losses = returns < 0
    gross_win = float(returns[wins].sum()) if wins.any() else 0.0
    gross_loss = float(abs(returns[losses].sum())) if losses.any() else 0.0
    profit_factor = round(gross_win / gross_loss, 3) if gross_loss > 0 else None
    equity = np.cumprod(1.0 + returns / 100.0)
    peak = np.maximum.accumulate(equity)
    drawdown = float(((equity / peak) - 1.0).min() * 100.0) if len(equity) else None
    t_excess = None
    if len(excess) > 2 and float(np.std(excess, ddof=1)) > 0:
        t_excess = round(float(np.mean(excess) / (np.std(excess, ddof=1) / math.sqrt(len(excess)))), 3)
    return {
        "trades": int(len(returns)),
        "win_rate": round(float(wins.mean()) * 100.0, 2),
        "avg_return": round(float(returns.mean()), 3),
        "median_return": round(float(np.median(returns)), 3),
        "profit_factor": profit_factor,
        "avg_excess": round(float(excess.mean()), 3) if len(excess) else None,
        "t_excess": t_excess,
        "max_drawdown": round(drawdown, 2) if drawdown is not None else None,
    }


def _load_symbol(symbol: str, bars: int) -> tuple[str, pd.DataFrame] | None:
    try:
        frame, _ = ds.get_tencent_history(symbol, "day", bars)
        if frame.empty or len(frame) < 120:
            return None
        return symbol, frame
    except Exception:
        return None


def _prepare(
    frame: pd.DataFrame,
    symbol: str,
    name: str,
    cooldown: int,
    st_period: int = 10,
    st_multiplier: float = 3.0,
    volume_threshold: float = 1.2,
    body_threshold: float = 0.5,
    require_weekly: bool = True,
) -> pd.DataFrame:
    data = compute_indicators(frame, st_period=st_period, st_multiplier=st_multiplier)
    data = attach_signal_quality(
        data,
        symbol,
        name=name,
        cooldown_days=cooldown,
        volume_threshold=volume_threshold,
        body_threshold=body_threshold,
        require_weekly=require_weekly,
    )
    return data


def _collect_trades(
    data: pd.DataFrame,
    index_close: dict[str, float],
    hold_days: int,
    start: int,
    signal_column: str,
    skip_limit_entry: bool = True,
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    n = len(data)
    if n <= start + hold_days + 1:
        return trades
    signal = data[signal_column].fillna(False).to_numpy(dtype=bool)
    for i in range(start, n - hold_days - 1):
        if not signal[i]:
            continue
        entry_i = i + 1
        exit_i = i + 1 + hold_days - 1
        entry = float(data["open"].iloc[entry_i])
        exit_price = float(data["close"].iloc[exit_i])
        if not (np.isfinite(entry) and np.isfinite(exit_price) and entry > 0):
            continue
        if skip_limit_entry:
            limit_up = data["limit_up_price"].iloc[entry_i]
            if np.isfinite(float(limit_up)) and entry >= float(limit_up) - 0.02:
                continue
        entry_date = str(data["date"].iloc[entry_i])
        exit_date = str(data["date"].iloc[exit_i])
        stock_return = (exit_price / entry - 1.0) * 100.0
        index_entry = index_close.get(entry_date)
        index_exit = index_close.get(exit_date)
        excess = None
        if index_entry and index_exit and index_entry > 0:
            index_return = (index_exit / index_entry - 1.0) * 100.0
            excess = stock_return - index_return
        trades.append(
            {
                "symbol": str(data["symbol"].iloc[0]) if "symbol" in data.columns else "",
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry": round(entry, 3),
                "exit": round(exit_price, 3),
                "return_pct": round(stock_return, 4),
                "excess_pct": round(excess, 4) if excess is not None else None,
            }
        )
    return trades


def run(
    universe: str = "hs300",
    bars: int = 640,
    hold_days: int = 10,
    cooldown: int = 10,
    workers: int = 8,
    start: int = 70,
    limit: int | None = None,
    st_period: int = 10,
    st_multiplier: float = 3.0,
    volume_threshold: float = 1.2,
    body_threshold: float = 0.5,
    require_weekly: bool = True,
) -> dict[str, Any]:
    symbols = ds.get_universe(universe)
    if limit:
        symbols = symbols[:limit]
    index_frame, _ = ds.get_tencent_history("000001.SH", "day", bars)
    index_frame = compute_indicators(index_frame)
    index_close = {
        str(row.date): float(row.close)
        for row in index_frame.itertuples(index=False)
        if np.isfinite(float(row.close))
    }

    frames: list[tuple[str, pd.DataFrame]] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="backtest") as executor:
        futures = {executor.submit(_load_symbol, item["symbol"], bars): item for item in symbols}
        for future in as_completed(futures):
            item = futures[future]
            try:
                loaded = future.result()
            except Exception:
                loaded = None
            if loaded:
                frames.append(loaded)
    print(f"loaded {len(frames)}/{len(symbols)} symbols in {time.time() - started:.1f}s", flush=True)

    all_baseline: list[dict[str, Any]] = []
    all_filtered: list[dict[str, Any]] = []
    failed: list[str] = []
    window_start = None
    window_end = None
    names = {item["symbol"]: item.get("name", item["symbol"]) for item in symbols}

    for symbol, frame in frames:
        try:
            data = _prepare(
                frame,
                symbol,
                names.get(symbol, symbol),
                cooldown,
                st_period=st_period,
                st_multiplier=st_multiplier,
                volume_threshold=volume_threshold,
                body_threshold=body_threshold,
                require_weekly=require_weekly,
            )
            data["symbol"] = symbol
            # Baseline: same “new signal” trigger cadence, but no P0 quality gates.
            raw_baseline = (
                (data["close"] > data["ma20"])
                & (data["vol_ratio_5"] >= 1.2)
                & (data["body_ratio"] >= 0.5)
                & (data["close"] > data["open"])
            ).fillna(False).to_numpy(dtype=bool)
            data["baseline_fresh"] = _fresh(raw_baseline, cooldown)
            all_baseline.extend(
                _collect_trades(data, index_close, hold_days, start, "baseline_fresh")
            )
            all_filtered.extend(
                _collect_trades(data, index_close, hold_days, start, "fresh_signal")
            )
            if window_start is None:
                window_start = str(data["date"].iloc[start])
            window_end = str(data["date"].iloc[-1])
        except Exception as exc:
            failed.append(f"{symbol}: {exc}")

    baseline = _stats(all_baseline)
    filtered = _stats(all_filtered)
    return {
        "universe": universe,
        "symbols_requested": len(symbols),
        "symbols_loaded": len(frames),
        "failed": failed[:20],
        "window": {"start": window_start, "end": window_end, "bars": bars, "hold_days": hold_days, "cooldown": cooldown},
        "baseline": baseline,
        "filtered": filtered,
        "baseline_trades": all_baseline,
        "filtered_trades": all_filtered,
        "generated_at": ds.now_text(),
    }


def _markdown(result: dict[str, Any]) -> str:
    def row(label: str, key: str) -> str:
        b = result["baseline"].get(key)
        f = result["filtered"].get(key)
        return f"| {label} | {b} | {f} |"

    lines = [
        "# P0 日线信号质量过滤器 · 回测报告",
        "",
        f"- 股票池：{result['universe']}（请求 {result['symbols_requested']} 只，成功 {result['symbols_loaded']} 只）",
        f"- 数据窗口：{result['window']['start']} 至 {result['window']['end']}，{result['window']['bars']} 根日线",
        f"- 交易规则：信号日收盘后，次日开盘买入；持有 {result['window']['hold_days']} 个交易日；同票冷却 {result['window']['cooldown']} 个交易日",
        "- 基准：上证指数（000001.SH），按同一持仓区间计算超额收益",
        "- 数据源：腾讯财经前复权日线（640 根上限）",
        "",
        "| 指标 | 基线（仅均线+量能+实体） | P0 过滤（日线ST+周线ST+VWAP+量能+实体） |",
        "|---|---:|---:|",
        row("交易数", "trades"),
        row("胜率 %", "win_rate"),
        row("平均单笔收益 %", "avg_return"),
        row("单笔收益中位数 %", "median_return"),
        row("盈亏比 PF", "profit_factor"),
        row("平均超额收益 %", "avg_excess"),
        row("超额 t 值", "t_excess"),
        row("交易序列最大回撤 %", "max_drawdown"),
        "",
        "## 口径说明",
        "",
        "- 基线使用“收盘站上 MA20 + 5 日量比 ≥1.2 + 实体 ≥50% + 阳线”的首次触发，并应用同样的 10 日冷却，保证触发节奏可比。",
        "- P0 过滤使用日线 Supertrend(10,3.0) 多头、上一完整周周线 Supertrend 多头、收盘高于 20 日 VWAP 与当日典型价、量比 ≥1.2（前 20 日均量不含当日）、实体 ≥50%。",
        "- 涨停或一字板当日不生成信号；次日开盘若已在涨停价附近，则跳过该笔，避免假设可以追入。",
        "- VWAP 使用腾讯日线的典型价×成交量估算，腾讯日线没有成交额字段；这是估算口径，不是交易所逐笔成交额口径。",
        "- 回测不包含佣金、印花税、滑点和停牌无法成交等真实摩擦，只用于比较过滤器是否有增量信息。",
        "",
        "## 仍需补齐",
        "",
        "- 腾讯日线最多 640 根，本报告有效信号窗口约 2.3 年；严格的 3 年样本外需要 BaoStock 1000 根或本地数据湖。",
        "- 需要再做参数扰动（ATR 倍数、量能门槛、实体门槛）与分年度稳定性，避免单一路径过拟合。",
    ]
    if result.get("failed"):
        lines += ["", "## 失败标的", "", *[f"- {item}" for item in result["failed"]]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0 signal-quality filter backtest")
    parser.add_argument("--universe", default="hs300")
    parser.add_argument("--bars", type=int, default=640)
    parser.add_argument("--hold", type=int, default=10)
    parser.add_argument("--cooldown", type=int, default=10)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--start", type=int, default=70)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--st-period", type=int, default=10)
    parser.add_argument("--st-multiplier", type=float, default=3.0)
    parser.add_argument("--volume-threshold", type=float, default=1.2)
    parser.add_argument("--body-threshold", type=float, default=0.5)
    parser.add_argument("--no-weekly", action="store_true")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "reports"))
    args = parser.parse_args(argv)

    result = run(
        universe=args.universe,
        bars=args.bars,
        hold_days=args.hold,
        cooldown=args.cooldown,
        workers=args.workers,
        start=args.start,
        limit=args.limit,
        st_period=args.st_period,
        st_multiplier=args.st_multiplier,
        volume_threshold=args.volume_threshold,
        body_threshold=args.body_threshold,
        require_weekly=not args.no_weekly,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signal_backtest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "signal_backtest.md").write_text(_markdown(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("symbols_loaded", "window", "baseline", "filtered")}, ensure_ascii=False, indent=2))
    print(f"report: {out_dir / 'signal_backtest.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
