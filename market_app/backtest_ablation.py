from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from . import data_sources as ds
from .backtest_signal import (
    _collect_trades,
    _fresh,
    _load_index,
    _load_symbol,
    _prepare,
    _stats,
)
from .costs import CostModel
from .indicators import compute_indicators


STEPS = [
    ("daily", "日线 Supertrend", ["daily_trend"]),
    ("weekly", "+ 周线 Supertrend", ["daily_trend", "weekly_trend"]),
    ("vwap", "+ 20 日 VWAP / 当日均价", ["daily_trend", "weekly_trend", "vwap"]),
    ("volume", "+ 量比 1.2", ["daily_trend", "weekly_trend", "vwap", "volume"]),
    ("body", "+ 实体占比 50%（P0 完整）", ["daily_trend", "weekly_trend", "vwap", "volume", "body"]),
]

COMBOS = [
    ("daily", "日线", ["daily_trend"]),
    ("dw", "日线 + 周线", ["daily_trend", "weekly_trend"]),
    ("dwv", "日线 + 周线 + VWAP", ["daily_trend", "weekly_trend", "vwap"]),
    ("dwb", "日线 + 周线 + 实体", ["daily_trend", "weekly_trend", "body"]),
    ("dwn", "日线 + 周线 + 量比", ["daily_trend", "weekly_trend", "volume"]),
    ("dwbn", "日线 + 周线 + 实体 + 量比", ["daily_trend", "weekly_trend", "body", "volume"]),
    ("dwvn", "日线 + 周线 + VWAP + 量比", ["daily_trend", "weekly_trend", "vwap", "volume"]),
    ("full", "日线 + 周线 + VWAP + 量比 + 实体（P0）", ["daily_trend", "weekly_trend", "vwap", "volume", "body"]),
]


def _combo_signal(data: "Any", gates: list[str], cooldown: int) -> np.ndarray:
    """按真实策略口径，在所有过滤同时满足后重新计算新信号。"""
    mask = data["gate_tradeable"].fillna(False).to_numpy(dtype=bool)
    for gate in gates:
        mask &= data[f"gate_{gate}"].fillna(False).to_numpy(dtype=bool)
    return _fresh(mask, cooldown)


def _signal_for(data: "Any", gates: list[str], cooldown: int) -> np.ndarray:
    """固定日线触发事件，再逐一叠加过滤器。

    每层都从同一批“日线 Supertrend 新信号”出发，避免加入过滤器后因
    冷却重置反而制造更多新信号，导致归因被污染。
    """
    base = (
        data["gate_daily_trend"].fillna(False).to_numpy(dtype=bool)
        & data["gate_tradeable"].fillna(False).to_numpy(dtype=bool)
    )
    mask = _fresh(base, cooldown)
    for gate in gates:
        if gate == "daily_trend":
            continue
        mask &= data[f"gate_{gate}"].fillna(False).to_numpy(dtype=bool)
    return mask


def run(
    universe: str = "hs300",
    bars: int = 320,
    hold_days: int = 10,
    cooldown: int = 10,
    start: int = 70,
    limit: int = 300,
    source: str = "cache",
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

    prepared = []
    for symbol, frame in frames:
        data = _prepare(frame, symbol, names.get(symbol, symbol), cooldown, require_weekly=True)
        prepared.append((symbol, data))

    results: list[dict[str, Any]] = []
    for key, label, gates in STEPS:
        trades: list[dict[str, Any]] = []
        signal_count = 0
        for symbol, data in prepared:
            data = data.copy()
            data["ablation_signal"] = _signal_for(data, gates, cooldown)
            step_trades, diagnostics = _collect_trades(
                data, index_close, hold_days, start, "ablation_signal", model
            )
            trades.extend(step_trades)
            signal_count += int(diagnostics["signals"])
        stats = _stats(trades)
        results.append({
            "key": key,
            "label": label,
            "gates": gates,
            "signals": signal_count,
            **stats,
        })

    combinations: list[dict[str, Any]] = []
    for key, label, gates in COMBOS:
        trades = []
        signal_count = 0
        for symbol, data in prepared:
            data = data.copy()
            data["combo_signal"] = _combo_signal(data, gates, cooldown)
            combo_trades, diagnostics = _collect_trades(
                data, index_close, hold_days, start, "combo_signal", model
            )
            trades.extend(combo_trades)
            signal_count += int(diagnostics["signals"])
        stats = _stats(trades)
        combinations.append({
            "key": key,
            "label": label,
            "gates": gates,
            "signals": signal_count,
            **stats,
        })

    previous_net_avg = None
    for item in results:
        net_avg = item["net"].get("avg_return")
        item["delta_vs_previous_net_avg"] = (
            round(float(net_avg) - float(previous_net_avg), 3)
            if net_avg is not None and previous_net_avg is not None
            else None
        )
        previous_net_avg = net_avg

    return {
        "universe": universe,
        "bars": bars,
        "hold_days": hold_days,
        "cooldown": cooldown,
        "symbols_requested": limit,
        "symbols_loaded": len(frames),
        "from": str(index_frame["date"].iloc[start]) if len(index_frame) > start else None,
        "to": str(index_frame["date"].iloc[-1]) if len(index_frame) else None,
        "cost_model": model.as_dict() if hasattr(model, "as_dict") else {},
        "baseline": results[0],
        "steps": results,
        "combinations": combinations,
    }


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# P0-3 消融实验（成本后）",
        "",
        f"- 股票池：{result['universe']} 前 {result['symbols_loaded']} 只",
        f"- 窗口：{result['from']} 至 {result['to']}，{result['bars']} 根日线",
        f"- 交易规则：t 日收盘信号，t+1 开盘成交，持有 {result['hold_days']} 个交易日，同票冷却 {result['cooldown']} 日",
        "- 成本口径：佣金万 2.5（最低 5 元）、印花税卖出 0.05%、过户费 0.001% 双边、滑点单边 0.1%",
        "",
        "| 逐步加入的过滤 | 信号数 | 交易数 | 净胜率 % | 净均收益 % | 净 PF | 净超额 % | 净超额 t | 相比上一步净均变化 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in result["steps"]:
        net = item["net"]
        lines.append(
            f"| {item['label']} | {item['signals']} | {item['trades']} | "
            f"{net.get('win_rate')} | {net.get('avg_return')} | {net.get('profit_factor')} | "
            f"{net.get('avg_excess')} | {net.get('t_excess')} | {item.get('delta_vs_previous_net_avg')} |"
        )
    lines += [
        "",
        "说明：这是单条日线路径上的逐步消融，不是参数网格搜索；每一行只增加一个过滤条件，交易和成本规则保持不变。",
        "如果某一层加入后净均收益下降，说明该过滤器在当前样本上没有边际贡献，应降级为“只展示”，而不是继续硬过滤。",
        "",
        "## 真实策略组合（每组独立重算新信号）",
        "",
        "| 组合 | 信号数 | 交易数 | 净胜率 % | 净均收益 % | 净 PF | 净超额 % | 净超额 t |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in result.get("combinations", []):
        net = item["net"]
        lines.append(
            f"| {item['label']} | {item['signals']} | {item['trades']} | "
            f"{net.get('win_rate')} | {net.get('avg_return')} | {net.get('profit_factor')} | "
            f"{net.get('avg_excess')} | {net.get('t_excess')} |"
        )
    lines += [
        "",
        "这一张表才是实际会落地的策略口径：组合内的过滤必须同时成立，再从“不合格→合格”的切换点记新信号。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="hs300")
    parser.add_argument("--bars", type=int, default=320)
    parser.add_argument("--hold", type=int, default=10)
    parser.add_argument("--cooldown", type=int, default=10)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--source", choices=("auto", "tencent", "baostock", "cache"), default="cache")
    parser.add_argument("--commission-rate", type=float, default=0.00025)
    parser.add_argument("--min-commission", type=float, default=5.0)
    parser.add_argument("--stamp-rate", type=float, default=0.0005)
    parser.add_argument("--transfer-rate", type=float, default=0.00001)
    parser.add_argument("--slippage", type=float, default=0.001)
    parser.add_argument("--capital", type=float, default=100000.0)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "reports" / "p0_ablation"))
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
    (out_dir / "ablation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "ablation.md").write_text(markdown(result), encoding="utf-8")
    print(markdown(result))
    print(f"report: {out_dir / 'ablation.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
