"""V3.9.1 walk-forward rolling splits."""
from __future__ import annotations


def rolling_splits(
    dates,
    train: int = 252,
    val: int = 63,
    test: int = 63,
    step: int = 63,
):
    """按时间顺序滚动切分 (train_idx, val_idx, test_idx)。"""
    n = len(dates)
    splits = []
    start = 0
    while start + train + val + test <= n:
        train_idx = list(range(start, start + train))
        val_idx = list(range(start + train, start + train + val))
        test_idx = list(range(start + train + val, start + train + val + test))
        splits.append((train_idx, val_idx, test_idx))
        start += step
    return splits


# ============================================================================
# V3.9.2 WalkForwardValidator (Alpha Research Engine)
# ============================================================================
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 504; validation_days: int = 126; test_days: int = 126
    step_days: int = 63; purge_days: int = 5; embargo_days: int = 5; min_windows: int = 3


@dataclass
class WalkForwardWindow:
    window_id: int; train: pd.DataFrame; validation: pd.DataFrame; test: pd.DataFrame
    purged: pd.DataFrame; embargo: pd.DataFrame; metadata: dict = field(default_factory=dict)


@dataclass
class WalkForwardResult:
    alpha: Any; windows: list; passed: bool; summary: dict


def _wf_eval(a, df):
    y = a(df) if callable(a) else a.evaluate(df) if hasattr(a, "evaluate") else df[a]
    if isinstance(y, pd.DataFrame):
        y = y.iloc[:, 0]
    return pd.Series(y, index=df.index, dtype=float)


def _ic(s, t):
    z = pd.concat([s, t], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    return np.nan if len(z) < 3 else float(z.iloc[:, 0].rank().corr(z.iloc[:, 1].rank()))


def calculate_turnover(previous_holdings, current_holdings):
    if not previous_holdings and not current_holdings:
        return 0.
    return len(set(previous_holdings) ^ set(current_holdings)) / max(len(set(previous_holdings) | set(current_holdings)), 1)


def calculate_quantile_spread(df, signal_col="signal", target_col="forward_return", q=5):
    vals = []
    for _, d in df.groupby("date"):
        z = d[[signal_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(z) < q * 2:
            continue
        try:
            lab = pd.qcut(z[signal_col].rank(method="first"), q=q, labels=False)
        except ValueError:
            continue
        z = z.assign(_q=lab)
        vals.append(float(z.loc[z._q == q - 1, target_col].mean() - z.loc[z._q == 0, target_col].mean()))
    return float(np.mean(vals)) if vals else np.nan


class WalkForwardValidator:
    def __init__(self, train_days=504, validation_days=126, test_days=126, step_days=63,
                 purge_days=5, embargo_days=5, min_windows=3, config=None):
        self.config = config or WalkForwardConfig(train_days, validation_days, test_days, step_days,
                                                 purge_days, embargo_days, min_windows)

    def build_windows(self, panel):
        x = panel.copy(); x.date = pd.to_datetime(x.date); x.code = x.code.astype(str)
        x = x.sort_values(["date", "code"])
        dates = pd.Index(sorted(x.date.unique())); c = self.config
        need = c.train_days + c.purge_days + c.validation_days + c.embargo_days + c.test_days
        out = []; start = 0; wid = 0
        while start + need <= len(dates):
            a = start; b = a + c.train_days; p = b + c.purge_days; v = p + c.validation_days
            e = v + c.embargo_days; t = e + c.test_days
            take = lambda ds: x[x.date.isin(ds)].copy()
            tr, pu, va, em, te = map(take, [dates[a:b], dates[b:p], dates[p:v], dates[v:e], dates[e:t]])
            out.append(WalkForwardWindow(wid, tr, va, te, pu, em, {
                "train_start": str(dates[a]), "train_end": str(dates[b - 1]),
                "test_start": str(dates[e]), "test_end": str(dates[t - 1])}))
            wid += 1; start += c.step_days
        return out

    def validate(self, alpha, panel, target_col="forward_return_5d"):
        x = panel.copy()
        if target_col not in x:
            from backtest.returns import calculate_forward_returns
            x[target_col] = calculate_forward_returns(x, 5, "next_open").to_numpy()
        rows = []
        for w in self.build_windows(x):
            for stage, df in [("train", w.train), ("validation", w.validation), ("test", w.test)]:
                z = df.copy(); z["signal"] = _wf_eval(alpha, z).to_numpy(); ics = []
                for _, d in z.groupby("date"):
                    q = _ic(d.signal, d[target_col])
                    if pd.notna(q):
                        ics.append(q)
                spread = calculate_quantile_spread(z, "signal", target_col)
                sd = np.std(ics, ddof=1) if len(ics) > 1 else np.nan
                rows.append({"window_id": w.window_id, "stage": stage,
                             "ic": np.mean(ics) if ics else np.nan,
                             "icir": np.mean(ics) / sd if len(ics) > 1 and sd > 0 else np.nan,
                             "quantile_spread": spread, "n_days": len(ics)})
        m = pd.DataFrame(rows); test = m[m.stage == "test"]
        passed = (len(test) >= self.config.min_windows
                  and test.ic.notna().sum() >= self.config.min_windows
                  and test.ic.mean() >= .02
                  and test.icir.dropna().mean() >= .20
                  and test.quantile_spread.dropna().mean() >= .003)
        windows = self.build_windows(x)
        return WalkForwardResult(alpha, windows, bool(passed), {
            "n_windows": len(windows), "n_test_windows": len(test),
            "mean_test_ic": float(test.ic.mean()) if len(test) else np.nan,
            "mean_test_icir": float(test.icir.mean()) if len(test) else np.nan,
            "mean_test_quantile_spread": float(test.quantile_spread.mean()) if len(test) else np.nan,
            "passed": bool(passed), "metrics": m.to_dict("records")})

    def run_with_callback(self, panel, callback):
        return [callback(w) for w in self.build_windows(panel)]


def evaluate_alpha_oos(alpha, panel, min_ic=.02, min_train_retention=.30, target_col="forward_return_5d"):
    x = panel.copy(); x.date = pd.to_datetime(x.date)
    if target_col not in x:
        from backtest.returns import calculate_forward_returns
        x[target_col] = calculate_forward_returns(x, 5, "next_open").to_numpy()
    dates = pd.Index(sorted(x.date.unique())); n = len(dates)
    tr = int(n * .6); te = int(n * .8)

    def ev(df):
        z = df.copy(); z["signal"] = _wf_eval(alpha, z)
        vals = [_ic(d.signal, d[target_col]) for _, d in z.groupby("date")]
        vals = [v for v in vals if pd.notna(v)]
        return np.mean(vals) if vals else np.nan

    train_ic = ev(x[x.date.isin(dates[:tr])]); oos_ic = ev(x[x.date.isin(dates[te:])])
    passed = pd.notna(oos_ic) and abs(oos_ic) >= min_ic and (pd.isna(train_ic) or abs(oos_ic) >= min_train_retention * abs(train_ic))
    return type("OOSResult", (), {"alpha": alpha, "train_ic": train_ic,
                                  "oos_ic": oos_ic, "passed": bool(passed)})()
