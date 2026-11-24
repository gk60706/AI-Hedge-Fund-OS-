"""V3.9.1 backtest portfolio: top-quantile equal-weight with T+1 open execution."""
from __future__ import annotations

import pandas as pd

from backtest.costs import transaction_cost


def top_quantile_portfolio(
    panel,
    signal,
    quantile=0.80,
    initial_cash=1_000_000,
    slippage=0.0005,
):
    """T 日信号 → T+1 开盘等权买入（dump verbatim），返回 (equity_curve, trades_df)。"""
    x = panel.copy().sort_values(["date", "code"]).reset_index(drop=True)
    signal = signal.reindex(panel.index).reset_index(drop=True)
    x["signal"] = signal
    x["next_open"] = x.groupby("code")["open"].shift(-1)
    x["next_date"] = x.groupby("code")["date"].shift(-1)
    equity = float(initial_cash)
    curve = []
    trades = []
    for date, day in x.groupby("date"):
        valid = day.dropna(subset=["signal", "next_open"])
        if valid.empty:
            curve.append((date, equity))
            continue
        threshold = valid["signal"].quantile(quantile)
        picks = valid[valid["signal"] >= threshold]
        if picks.empty:
            curve.append((date, equity))
            continue
        weight = 1.0 / len(picks)
        daily_return = 0.0
        for _, row in picks.iterrows():
            entry = float(row["next_open"]) * (1 + slippage)
            exit_price = float(row["close"])
            gross_return = exit_price / entry - 1
            notional = equity * weight
            buy_cost = transaction_cost(notional, "BUY")
            net_return = gross_return - buy_cost / notional
            daily_return += weight * net_return
            trades.append(
                {
                    "signal_date": date,
                    "code": row["code"],
                    "weight": weight,
                    "entry": entry,
                    "exit": exit_price,
                    "gross_return": gross_return,
                    "net_return": net_return,
                }
            )
        equity *= 1 + daily_return
        curve.append((date, equity))
    equity_curve = pd.Series(dict(curve), dtype=float).sort_index()
    trades_df = pd.DataFrame(trades)
    return equity_curve, trades_df
