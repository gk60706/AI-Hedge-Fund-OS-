from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import data_sources as ds
from .backtest_signal import (
    _collect_trades,
    _fresh,
    _load_symbol,
    _prepare,
    _stats,
)
from .indicators import compute_indicators


VARIANTS: list[dict[str, Any]] = [
    {"name": "base", "st_period": 10, "st_multiplier": 3.0, "volume_threshold": 1.2, "body_threshold": 0.5},
    {"name": "vol_1.1", "st_period": 10, "st_multiplier": 3.0, "volume_threshold": 1.1, "body_threshold": 0.5},
    {"name": "vol_1.3", "st_period": 10, "st_multiplier": 3.0, "volume_threshold": 1.3, "body_threshold": 0.5},
    {"name": "body_45", "st_period": 10, "st_multiplier": 3.0, "volume_threshold": 1.2, "body_threshold": 0.45},
    {"name": "body_55", "st_period": 10, "st_multiplier": 3.0, "volume_threshold": 1.2, "body_threshold": 0.55},
    {"name": "st_2.5", "st_period": 10, "st_multiplier": 2.5, "volume_threshold": 1.2, "body_threshold": 0.5},
    {"name": "st_3.5", "st_period": 10, "st_multiplier": 3.5, "volume_threshold": 1.2, "body_threshold": 0.5},
]


def run(universe: str = "hs300", bars: int = 640, hold_days: int = 10, cooldown: int = 10, start: int = 70, limit: int = 100) -> dict[str, Any]:
    symbols = ds.get_universe(universe)[:limit]
    names = {item["symbol"]: item.get("name", item["symbol"]) for item in symbols}
    index_frame, _ = ds.get_tencent_history("000001.SH", "day", bars)
    index_frame = compute_indicators(index_frame)
    index_close = {
        str(row.date): float(row.close)
        for row in index_frame.itertuples(index=False)
        if float(row.close) == float(row.close)
    }

    frames = []
    for item in symbols:
        loaded = _load_symbol(item["symbol"], bars)
        if loaded:
            frames.append(loaded)
    print(f"loaded {len(frames)}/{len(symbols)} symbols", flush=True)

    baseline_trades: list[dict[str, Any]] = []
    for symbol, frame in frames:
        data = _prepare(frame, symbol, names.get(symbol, symbol), cooldown)
        raw = (
            (data["close"] > data["ma20"])
            & (data["vol_ratio_5"] >= 1.2)
            & (data["body_ratio"] >= 0.5)
            & (data["close"] > data["open"])
        ).fillna(False).to_numpy(dtype=bool)
        data["baseline_fresh"] = _fresh(raw, cooldown)
        baseline_trades.extend(_collect_trades(data, index_close, hold_days, start, "baseline_fresh"))
    baseline = _stats(baseline_trades)

    results = []
    for variant in VARIANTS:
        trades: list[dict[str, Any]] = []
        for symbol, frame in frames:
            data = _prepare(
                frame,
                symbol,
                names.get(symbol, symbol),
                cooldown,
                st_period=variant["st_period"],
                st_multiplier=variant["st_multiplier"],
                volume_threshold=variant["volume_threshold"],
                body_threshold=variant["body_threshold"],
                require_weekly=True,
            )
            trades.extend(_collect_trades(data, index_close, hold_days, start, "fresh_signal"))
        stats = _stats(trades)
        edge_kept = (
            baseline.get("avg_excess") is not None
            and stats.get("avg_excess") is not None
            and stats["avg_excess"] > baseline["avg_excess"]
        )
        results.append({"variant": variant, **stats, "edge_kept": bool(edge_kept)})

    kept = sum(1 for item in results if item["edge_kept"])
    return {
        "universe": universe,
        "symbols_loaded": len(frames),
        "baseline": baseline,
        "variants": results,
        "edge_kept": kept,
        "edge_kept_pct": round(kept / len(results) * 100.0, 1),
        "generated_at": ds.now_text(),
    }


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# P0 信号质量过滤器 · 参数扰动",
        "",
        f"- 股票池：{result['universe']} 前 {result['symbols_loaded']} 只",
        f"- 基线平均超额收益：{result['baseline'].get('avg_excess')}%",
        f"- 参数组保留超额的比例：{result['edge_kept_pct']}%（{result['edge_kept']}/{len(result['variants'])}）",
        "",
        "| 参数组 | 交易数 | 平均收益 % | PF | 平均超额 % | 超额 t | 保留超额 |",
        "|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for item in result["variants"]:
        v = item["variant"]
        label = f"ST {v['st_multiplier']} / 量能 {v['volume_threshold']} / 实体 {v['body_threshold']}"
        lines.append(
            f"| {label} | {item['trades']} | {item['avg_return']} | {item['profit_factor']} | "
            f"{item['avg_excess']} | {item['t_excess']} | {'是' if item['edge_kept'] else '否'} |"
        )
    lines += [
        "",
        "说明：参数组只改变 P0 过滤器的 ATR 倍数、量能门槛和实体门槛，基线与交易规则保持不变。",
        "“保留超额”指该参数组的平均超额收益高于同口径基线；这是稳健性检查，不是参数寻优。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="hs300")
    parser.add_argument("--bars", type=int, default=640)
    parser.add_argument("--hold", type=int, default=10)
    parser.add_argument("--cooldown", type=int, default=10)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "reports"))
    args = parser.parse_args()
    result = run(args.universe, args.bars, args.hold, args.cooldown, 70, args.limit)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signal_perturb.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "signal_perturb.md").write_text(markdown(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("symbols_loaded", "baseline", "variants", "edge_kept_pct")}, ensure_ascii=False, indent=2))
    print(f"report: {out_dir / 'signal_perturb.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
