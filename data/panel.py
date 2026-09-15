"""V3.9.1 cross-section panel: the core date x code research frame."""
from __future__ import annotations

import numpy as np
import pandas as pd


class CrossSectionPanel:
    def __init__(self, df: pd.DataFrame):
        if "date" not in df.columns or "code" not in df.columns or "close" not in df.columns:
            raise ValueError("Panel 必须包含 date / code / close 列")
        self.df = df.copy()

    def forward_return(self, horizon: int = 1) -> pd.Series:
        """T 日收盘到 T+horizon 的收益（按 code 分组 shift(-h)）。"""
        close = self.df.set_index(["date", "code"])["close"]
        shifted = close.groupby(level="code").shift(-horizon)
        return (shifted / close - 1.0).reset_index(name="forward_return")["forward_return"]

    def add_forward_return(self, horizon: int = 1) -> pd.DataFrame:
        df = self.df.copy()
        df["forward_return"] = self.forward_return(horizon)
        return df

    @staticmethod
    def rank(series: pd.Series, dates: pd.Series | None = None) -> pd.Series:
        """横截面排名：每个 date 内 rank(pct=True, method='average')。"""
        data = pd.DataFrame({"date": dates, "value": series}) if dates is not None else None
        if data is None:
            return series.rank(pct=True, method="average")
        return (
            data.groupby("date")["value"]
            .rank(pct=True, method="average")
            .reset_index(drop=True)
        )

    @staticmethod
    def zscore(series: pd.Series, dates: pd.Series | None = None) -> pd.Series:
        """横截面 z-score：每个 date 内 (x - mean) / std（std=0 或非有限 → NaN）。"""
        if dates is None:
            std = series.std(ddof=0)
            if std == 0 or not np.isfinite(std):
                return pd.Series(np.nan, index=series.index)
            return (series - series.mean()) / std
        frame = pd.DataFrame({"date": dates, "value": series})
        grouped = frame.groupby("date")["value"]
        mean = grouped.transform("mean")
        std = grouped.transform("std", ddof=0)
        out = (frame["value"] - mean) / std
        out.loc[std == 0] = np.nan
        out.loc[~np.isfinite(out)] = np.nan
        return out.reset_index(drop=True)

    @staticmethod
    def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
        clean = series.dropna()
        if len(clean) < 5:
            return series
        lo, hi = clean.quantile([lower, upper])
        return series.clip(lo, hi)


def make_demo_panel(
    n_stocks: int = 80,
    n_days: int = 900,
    seed: int = 42,
) -> pd.DataFrame:
    """V3.9.1 合成研究面板（演示用，明确不可推真实收益）。

    生成 date x code 面板：随机游走价格 + 带相关结构的合成因子
    （value / momentum / quality / volatility / liquidity / pe / pb）。
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=n_days)
    rows: list[dict] = []
    for i in range(n_stocks):
        code = f"{300000 + i}"
        returns = rng.normal(0.0003, 0.02, n_days)
        close = 10.0 * np.exp(np.cumsum(returns))
        open_ = np.concatenate([[10.0], close[:-1]])
        base = float(rng.normal(0.0, 1.0))
        for t, day in enumerate(dates):
            rows.append(
                {
                    "date": day,
                    "code": code,
                    "open": float(open_[t]),
                    "close": float(close[t]),
                    "volume": float(rng.uniform(1e5, 1e7)),
                    "amount": float(rng.uniform(1e6, 1e8)),
                    "turnover": float(rng.uniform(0.5, 10.0)),
                    "pe": float(rng.uniform(5.0, 60.0)),
                    "pb": float(rng.uniform(0.5, 8.0)),
                    "value": float(base + rng.normal(0.0, 1.0)),
                    "momentum": float(returns[t] * 100.0 + base * 0.5),
                    "quality": float(base + rng.normal(0.0, 1.0)),
                    "volatility": float(abs(rng.normal(0.02, 0.01))),
                    "liquidity": float(rng.uniform(0.0, 1.0)),
                }
            )
    return pd.DataFrame(rows)
