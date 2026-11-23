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
from .config import SCREEN_CACHE_DIR
from .costs import CostModel
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


def _metric_block(trades: list[dict[str, Any]], return_key: str, excess_key: str) -> dict[str, Any]:
    returns = np.array(
        [item[return_key] for item in trades if item.get(return_key) is not None],
        dtype=float,
    )
    returns = returns[np.isfinite(returns)]
    excess = np.array(
        [item[excess_key] for item in trades if item.get(excess_key) is not None],
        dtype=float,
    )
    excess = excess[np.isfinite(excess)]

    if len(returns) == 0:
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
        t_excess = round(
            float(np.mean(excess) / (np.std(excess, ddof=1) / math.sqrt(len(excess)))),
            3,
        )

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


def _stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        empty = _metric_block([], "gross_return_pct", "gross_excess_pct")
        return {
            "trades": 0,
            "gross": empty,
            "net": dict(empty),
            "avg_cost_drag_pct": None,
            # Backward-compatible aliases: old reports treated these as gross.
            "win_rate": None,
            "avg_return": None,
            "median_return": None,
            "profit_factor": None,
            "avg_excess": None,
            "t_excess": None,
            "max_drawdown": None,
        }

    # Thread completion order is nondeterministic; a drawdown path must use a
    # stable chronological order.
    trades = sorted(trades, key=lambda item: (item["exit_date"], item["entry_date"], item["symbol"]))
    gross = _metric_block(trades, "gross_return_pct", "gross_excess_pct")
    net = _metric_block(trades, "net_return_pct", "net_excess_pct")
    drags = [
        float(item["cost_drag_pct"])
        for item in trades
        if item.get("cost_drag_pct") is not None and np.isfinite(float(item["cost_drag_pct"]))
    ]
    result = {
        "trades": int(net["trades"]),
        "gross": gross,
        "net": net,
        "avg_cost_drag_pct": round(float(np.mean(drags)), 3) if drags else None,
    }
    # Keep old keys mapped to net; new reports should use .gross/.net explicitly.
    for key in ("win_rate", "avg_return", "median_return", "profit_factor", "avg_excess", "t_excess", "max_drawdown"):
        result[key] = net[key]
    return result


def _cache_path(symbol: str) -> Path:
    return SCREEN_CACHE_DIR / f"{symbol.replace('.', '_')}.csv"


def _load_symbol(symbol: str, bars: int, source: str = "auto") -> tuple[str, pd.DataFrame] | None:
    errors: list[str] = []

    if source in ("tencent", "auto") and bars <= 640:
        try:
            frame, _ = ds.get_tencent_history(symbol, "day", bars)
            if not frame.empty and len(frame) >= 120:
                return symbol, frame
            errors.append("腾讯 K 线不足 120 根")
        except Exception as exc:
            errors.append(f"腾讯: {exc}")

    if source in ("baostock", "auto"):
        try:
            frame, _ = ds.get_baostock_history(symbol, "day", bars)
            if not frame.empty and len(frame) >= 120:
                return symbol, frame
            errors.append("BaoStock K 线不足 120 根")
        except Exception as exc:
            errors.append(f"BaoStock: {exc}")

    if source in ("cache", "auto"):
        path = _cache_path(symbol)
        if path.is_file():
            try:
                frame = pd.read_csv(path)
                if not frame.empty and len(frame) >= 120:
                    return symbol, frame
                errors.append("本地缓存不足 120 根")
            except Exception as exc:
                errors.append(f"缓存: {exc}")

    if errors:
        print(f"skip {symbol}: {' | '.join(errors[:2])}", flush=True)
    return None


def _load_index(bars: int, source: str = "auto") -> pd.DataFrame:
    if source in ("tencent", "auto") and bars <= 640:
        try:
            frame, _ = ds.get_tencent_history("000001.SH", "day", bars)
            if not frame.empty:
                return frame
        except Exception:
            pass
    if source in ("baostock", "auto"):
        try:
            frame, _ = ds.get_baostock_history("000001.SH", "day", bars)
            if not frame.empty:
                return frame
        except Exception:
            pass
    if source in ("cache", "auto"):
        path = _cache_path("000001.SH")
        if path.is_file():
            frame = pd.read_csv(path)
            if not frame.empty:
                return frame
    raise RuntimeError("无法获取上证指数历史数据")


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
    core_only: bool = False,
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
        core_only=core_only,
    )
    return data


def _date_gap_days(left: str, right: str) -> int:
    try:
        return int((pd.Timestamp(right) - pd.Timestamp(left)).days)
    except Exception:
        return 0


def _collect_trades(
    data: pd.DataFrame,
    index_close: dict[str, float],
    hold_days: int,
    start: int,
    signal_column: str,
    cost_model: CostModel,
    max_exit_delay: int = 10,
    max_entry_gap_days: int = 12,
    skip_limit_entry: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    trades: list[dict[str, Any]] = []
    diagnostics = {
        "signals": 0,
        "entry_limit_up": 0,
        "entry_gap": 0,
        "unclosed_limit_down": 0,
        "invalid_price": 0,
        "after_end": 0,
    }
    n = len(data)
    if n <= start + hold_days + 1:
        return trades, diagnostics

    signal = data[signal_column].fillna(False).to_numpy(dtype=bool)
    for i in range(start, n - hold_days - 1):
        if not signal[i]:
            continue
        diagnostics["signals"] += 1

        entry_i = i + 1
        if entry_i >= n:
            diagnostics["after_end"] += 1
            continue

        signal_date = str(data["date"].iloc[i])
        entry_date = str(data["date"].iloc[entry_i])
        gap = _date_gap_days(signal_date, entry_date)
        if max_entry_gap_days > 0 and gap > max_entry_gap_days:
            diagnostics["entry_gap"] += 1
            continue

        entry = float(data["open"].iloc[entry_i])
        if not (np.isfinite(entry) and entry > 0):
            diagnostics["invalid_price"] += 1
            continue

        if skip_limit_entry:
            limit_up = float(data["limit_up_price"].iloc[entry_i])
            one_word = bool(data["one_word"].iloc[entry_i]) if "one_word" in data.columns else False
            if np.isfinite(limit_up) and entry >= limit_up - 0.02:
                diagnostics["entry_limit_up"] += 1
                continue
            if one_word:
                diagnostics["entry_limit_up"] += 1
                continue

        base_exit_i = i + 1 + hold_days - 1
        exit_i = base_exit_i
        exit_price = None
        while exit_i < n and exit_i <= base_exit_i + max(0, max_exit_delay):
            close = float(data["close"].iloc[exit_i])
            limit_down = float(data["limit_down_price"].iloc[exit_i])
            one_word = bool(data["one_word"].iloc[exit_i]) if "one_word" in data.columns else False
            sellable = np.isfinite(close) and close > 0
            if np.isfinite(limit_down) and close <= limit_down + 0.02:
                sellable = False
            if one_word and np.isfinite(limit_down) and close <= limit_down + 0.02:
                sellable = False
            if sellable:
                exit_price = close
                break
            exit_i += 1

        if exit_price is None:
            diagnostics["unclosed_limit_down"] += 1
            continue

        cost = cost_model.trade_return(entry, exit_price)
        gross_return = float(cost["gross_return_pct"])
        net_return = float(cost["net_return_pct"])
        exit_date = str(data["date"].iloc[exit_i])
        index_entry = index_close.get(entry_date)
        index_exit = index_close.get(exit_date)
        gross_excess = None
        net_excess = None
        if index_entry and index_exit and index_entry > 0:
            index_return = (index_exit / index_entry - 1.0) * 100.0
            gross_excess = gross_return - index_return
            net_excess = net_return - index_return

        trades.append(
            {
                "symbol": str(data["symbol"].iloc[0]) if "symbol" in data.columns else "",
                "signal_date": signal_date,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry": round(entry, 3),
                "exit": round(exit_price, 3),
                "entry_fill": cost["entry_fill"],
                "exit_fill": cost["exit_fill"],
                "shares": cost["shares"],
                "buy_fees": cost["buy_fees"],
                "sell_fees": cost["sell_fees"],
                "total_fees": cost["total_fees"],
                "gross_return_pct": round(gross_return, 4),
                "net_return_pct": round(net_return, 4),
                "cost_drag_pct": round(gross_return - net_return, 4),
                "gross_excess_pct": round(gross_excess, 4) if gross_excess is not None else None,
                "net_excess_pct": round(net_excess, 4) if net_excess is not None else None,
                # Backward-compatible alias: old consumers treat return_pct as gross.
                "return_pct": round(gross_return, 4),
                "excess_pct": round(gross_excess, 4) if gross_excess is not None else None,
                "exit_delay_days": int(exit_i - base_exit_i),
            }
        )
    return trades, diagnostics


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
    core_only: bool = False,
    source: str = "auto",
    cost_model: CostModel | None = None,
    max_exit_delay: int = 10,
    max_entry_gap_days: int = 12,
) -> dict[str, Any]:
    symbols = ds.get_universe(universe)
    if limit:
        symbols = symbols[:limit]
    index_frame = _load_index(bars, source=source)
    index_frame = compute_indicators(index_frame)
    index_close = {
        str(row.date): float(row.close)
        for row in index_frame.itertuples(index=False)
        if np.isfinite(float(row.close))
    }

    frames: list[tuple[str, pd.DataFrame]] = []
    started = time.time()
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="backtest") as executor:
        futures = {executor.submit(_load_symbol, item["symbol"], bars, source): item for item in symbols}
        for future in as_completed(futures):
            item = futures[future]
            try:
                loaded = future.result()
            except Exception:
                loaded = None
            if loaded:
                frames.append(loaded)
    print(f"loaded {len(frames)}/{len(symbols)} symbols in {time.time() - started:.1f}s", flush=True)

    model = cost_model or CostModel()
    all_baseline: list[dict[str, Any]] = []
    all_filtered: list[dict[str, Any]] = []
    diagnostics_baseline = {
        "signals": 0, "entry_limit_up": 0, "entry_gap": 0,
        "unclosed_limit_down": 0, "invalid_price": 0, "after_end": 0,
    }
    diagnostics_filtered = {key: 0 for key in diagnostics_baseline}
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
                core_only=core_only,
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

            base_trades, base_diag = _collect_trades(
                data, index_close, hold_days, start, "baseline_fresh", model,
                max_exit_delay=max_exit_delay, max_entry_gap_days=max_entry_gap_days,
            )
            filt_trades, filt_diag = _collect_trades(
                data, index_close, hold_days, start, "fresh_signal", model,
                max_exit_delay=max_exit_delay, max_entry_gap_days=max_entry_gap_days,
            )
            all_baseline.extend(base_trades)
            all_filtered.extend(filt_trades)
            for key, value in base_diag.items():
                diagnostics_baseline[key] += value
            for key, value in filt_diag.items():
                diagnostics_filtered[key] += value

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
        "window": {
            "start": window_start,
            "end": window_end,
            "bars": bars,
            "hold_days": hold_days,
            "cooldown": cooldown,
            "source": source,
            "gate_mode": "core" if core_only else "strict",
            "max_exit_delay": max_exit_delay,
            "max_entry_gap_days": max_entry_gap_days,
        },
        "cost_model": model.as_dict(),
        "baseline": baseline,
        "filtered": filtered,
        "baseline_diagnostics": diagnostics_baseline,
        "filtered_diagnostics": diagnostics_filtered,
        "baseline_trades": all_baseline,
        "filtered_trades": all_filtered,
        "generated_at": ds.now_text(),
    }


def _markdown(result: dict[str, Any]) -> str:
    def block(side: str, kind: str) -> dict[str, Any]:
        return result[side][kind]

    def row(label: str, key: str) -> str:
        return (
            f"| {label} | {block('baseline', 'gross').get(key)} | "
            f"{block('baseline', 'net').get(key)} | "
            f"{block('filtered', 'gross').get(key)} | "
            f"{block('filtered', 'net').get(key)} |"
        )

    costs = result["cost_model"]
    diag_b = result.get("baseline_diagnostics", {})
    diag_f = result.get("filtered_diagnostics", {})
    lines = [
        "# P0 日线信号质量过滤器 · 成本后回测报告",
        "",
        f"- 股票池：{result['universe']}（请求 {result['symbols_requested']} 只，成功 {result['symbols_loaded']} 只）",
        f"- 数据窗口：{result['window']['start']} 至 {result['window']['end']}，{result['window']['bars']} 根日线",
        f"- 数据源：{result['window'].get('source', 'auto')}（腾讯优先，BaoStock 兜底，本地缓存兜底）",
        f"- 过滤模式：{result['window'].get('gate_mode', 'strict')}（core = 日线+周线+可交易；strict = 五灯全开 + 可交易）",
        f"- 交易规则：信号日收盘后，t+1 开盘成交；持有 {result['window']['hold_days']} 个交易日；同票冷却 {result['window']['cooldown']} 个交易日",
        "- 基准：上证指数（000001.SH），按同一持仓区间计算超额收益；指数口径为毛收益",
        "",
        "## 成本假设",
        "",
        f"- 佣金：{costs['commission_rate'] * 100:.4f}%，单笔最低 {costs['min_commission']:.2f} 元",
        f"- 印花税：卖出 {costs['stamp_duty_rate'] * 100:.4f}%",
        f"- 过户费：{costs['transfer_fee_rate'] * 100:.4f}%，双边",
        f"- 滑点：单边 {costs['slippage_rate'] * 100:.4f}%",
        f"- 每笔名义本金：{costs['capital']:.0f} 元；固定本金口径，不做复利",
        "",
        "| 指标 | 基线毛 | 基线净 | P0 毛 | P0 净 |",
        "|---|---:|---:|---:|---:|",
        row("交易数", "trades"),
        row("胜率 %", "win_rate"),
        row("平均单笔收益 %", "avg_return"),
        row("单笔收益中位数 %", "median_return"),
        row("盈亏比 PF", "profit_factor"),
        row("平均超额收益 %", "avg_excess"),
        row("超额 t 值", "t_excess"),
        row("交易序列最大回撤 %", "max_drawdown"),
        "",
        f"- 平均成本拖累：基线 {result['baseline'].get('avg_cost_drag_pct')} 个百分点，"
        f"P0 {result['filtered'].get('avg_cost_drag_pct')} 个百分点。",
        f"- 未成交/无效信号：基线 {diag_b.get('entry_limit_up', 0)} 个涨停买不到、"
        f"{diag_b.get('entry_gap', 0)} 个停牌/缺口过长、"
        f"{diag_b.get('unclosed_limit_down', 0)} 个跌停卖不掉；"
        f"P0 {diag_f.get('entry_limit_up', 0)} / {diag_f.get('entry_gap', 0)} / {diag_f.get('unclosed_limit_down', 0)}。",
        "",
        "## 口径说明",
        "",
        "- 基线使用“收盘站上 MA20 + 5 日量比 ≥1.2 + 实体 ≥50% + 阳线”的首次触发，并应用同样的 10 日冷却，保证触发节奏可比。",
        "- P0 过滤使用日线 Supertrend(10,3.0) 多头、上一完整周周线 Supertrend 多头、收盘高于 20 日 VWAP 与当日典型价、量比 ≥1.2（前 20 日均量不含当日）、实体 ≥50%。",
        "- 涨停或一字板当日不生成信号；t+1 开盘若已在涨停价附近或为一字板，则跳过该笔。",
        "- 跌停日不能卖出；若持有期结束日跌停/一字跌停，最多顺延 10 个交易日，仍无法卖出则该笔标记为未平仓，不计入收益。",
        "- 信号日与成交日相隔超过 12 个自然日，按停牌/长假异常跳过，避免把长期停牌后的开盘当成正常 t+1。",
        "- VWAP 优先使用 BaoStock 真实成交额；腾讯日线无成交额时用典型价×成交量估算，并在来源中标注。",
        "",
        "## 仍需补齐",
        "",
        "- 本报告只完成 P0-1：成本与成交约束。P0-2 的历史时点成分/退市股、P0-3 的消融与 Walk-forward 尚未完成，不能据此宣称策略已通过长期验证。",
        "- 腾讯日线最多 640 根；5 年样本应使用 BaoStock 1000+ 根，并补齐历史指数成分。",
        "- 参数扰动需要在本成本口径下重跑；当前 28.6% 的旧结果仍是毛收益口径。",
    ]
    if result.get("failed"):
        lines += ["", "## 失败标的", "", *[f"- {item}" for item in result["failed"]]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0 signal-quality filter backtest with costs")
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
    parser.add_argument("--gate-mode", choices=("core", "strict"), default="strict")
    parser.add_argument("--source", choices=("auto", "tencent", "baostock", "cache"), default="auto")
    parser.add_argument("--commission-rate", type=float, default=0.00025)
    parser.add_argument("--min-commission", type=float, default=5.0)
    parser.add_argument("--stamp-rate", type=float, default=0.0005)
    parser.add_argument("--transfer-rate", type=float, default=0.00001)
    parser.add_argument("--slippage", type=float, default=0.001)
    parser.add_argument("--capital", type=float, default=100000.0)
    parser.add_argument("--max-exit-delay", type=int, default=10)
    parser.add_argument("--max-entry-gap", type=int, default=12)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "reports"))
    args = parser.parse_args(argv)

    model = CostModel(
        commission_rate=args.commission_rate,
        min_commission=args.min_commission,
        stamp_duty_rate=args.stamp_rate,
        transfer_fee_rate=args.transfer_rate,
        slippage_rate=args.slippage,
        capital=args.capital,
    )
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
        core_only=args.gate_mode == "core",
        source=args.source,
        cost_model=model,
        max_exit_delay=args.max_exit_delay,
        max_entry_gap_days=args.max_entry_gap,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signal_backtest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "signal_backtest.md").write_text(_markdown(result), encoding="utf-8")
    print(json.dumps(
        {
            k: result[k]
            for k in ("symbols_loaded", "window", "cost_model", "baseline", "filtered", "baseline_diagnostics", "filtered_diagnostics")
        },
        ensure_ascii=False,
        indent=2,
    ))
    print(f"report: {out_dir / 'signal_backtest.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
