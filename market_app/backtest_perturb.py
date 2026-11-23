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
    _load_index,
    _prepare,
    _stats,
)
from .costs import CostModel
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


def run(
    universe: str = "hs300",
    bars: int = 640,
    hold_days: int = 10,
    cooldown: int = 10,
    start: int = 70,
    limit: int = 100,
    source: str = "auto",
    cost_model: CostModel | None = None,
) -> dict[str, Any]:
    symbols = ds.get_universe(universe)[:limit]
    names = {item["symbol"]: item.get("name", item["symbol"]) for item in symbols}
    index_frame = _load_index(bars, source=source)
    index_frame = compute_indicators(index_frame)
    index_close = {
        str(row.date): float(row.close)
        for row in index_frame.itertuples(index=False)
        if float(row.close) == float(row.close)
    }
    model = cost_model or CostModel()

    frames = []
    for item in symbols:
        loaded = _load_symbol(item["symbol"], bars, source)
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
        trades, _ = _collect_trades(
            data, index_close, hold_days, start, "baseline_fresh", model
        )
        baseline_trades.extend(trades)
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
            variant_trades, _ = _collect_trades(
                data, index_close, hold_days, start, "fresh_signal", model
            )
            trades.extend(variant_trades)
        stats = _stats(trades)
        base_excess = baseline.get("net", {}).get("avg_excess")
        var_excess = stats.get("net", {}).get("avg_excess")
        edge_kept = (
            base_excess is not None
            and var_excess is not None
            and var_excess > base_excess
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
    base = result["baseline"].get("net", {})
    lines = [
        "# P0 信号质量过滤器 · 成本后参数扰动",
        "",
        f"- 股票池：{result['universe']} 前 {result['symbols_loaded']} 只",
        f"- 成本口径：佣金 + 印花税 + 过户费 + 单边滑点，t+1 开盘成交",
        f"- 基线净超额收益：{base.get('avg_excess')}%",
        f"- 参数组保留净超额的比例：{result['edge_kept_pct']}%（{result['edge_kept']}/{len(result['variants'])}）",
        "",
        "| 参数组 | 交易数 | 毛均收益 % | 净均收益 % | 净 PF | 净超额 % | 净超额 t | 保留超额 |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for item in result["variants"]:
        v = item["variant"]
        label = f"ST {v['st_multiplier']} / 量能 {v['volume_threshold']} / 实体 {v['body_threshold']}"
        lines.append(
            f"| {label} | {item['trades']} | {item['gross'].get('avg_return')} | "
            f"{item['net'].get('avg_return')} | {item['net'].get('profit_factor')} | "
            f"{item['net'].get('avg_excess')} | {item['net'].get('t_excess')} | "
            f"{'是' if item['edge_kept'] else '否'} |"
        )
    lines += [
        "",
        "说明：参数组只改变 P0 过滤器的 ATR 倍数、量能门槛和实体门槛，基线与交易规则保持不变。",
        "“保留超额”指该参数组的成本后平均超额收益高于同口径基线；这是稳健性检查，不是参数寻优。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="hs300")
    parser.add_argument("--bars", type=int, default=640)
    parser.add_argument("--hold", type=int, default=10)
    parser.add_argument("--cooldown", type=int, default=10)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--source", choices=("auto", "tencent", "baostock", "cache"), default="auto")
    parser.add_argument("--commission-rate", type=float, default=0.00025)
    parser.add_argument("--min-commission", type=float, default=5.0)
    parser.add_argument("--stamp-rate", type=float, default=0.0005)
    parser.add_argument("--transfer-rate", type=float, default=0.00001)
    parser.add_argument("--slippage", type=float, default=0.001)
    parser.add_argument("--capital", type=float, default=100000.0)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "reports"))
    args = parser.parse_args()
    model = CostModel(
        commission_rate=args.commission_rate,
        min_commission=args.min_commission,
        stamp_duty_rate=args.stamp_rate,
        transfer_fee_rate=args.transfer_rate,
        slippage_rate=args.slippage,
        capital=args.capital,
    )
    result = run(args.universe, args.bars, args.hold, args.cooldown, 70, args.limit, args.source, model)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signal_perturb.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "signal_perturb.md").write_text(markdown(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("symbols_loaded", "baseline", "variants", "edge_kept_pct")}, ensure_ascii=False, indent=2))
    print(f"report: {out_dir / 'signal_perturb.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
