from __future__ import annotations
from typing import Iterable
import numpy as np
import pandas as pd

def _norm(df):
    if not {"date","code"} <= set(df.columns):
        raise ValueError("panel requires date and code")
    x=df.copy(); x["date"]=pd.to_datetime(x["date"]); x["code"]=x["code"].astype(str)
    return x.sort_values(["code","date"])

def calculate_forward_returns(df, horizon=1, entry="next_open", exit="future_close", price_col="close"):
    if horizon < 1: raise ValueError("horizon must be >= 1")
    x=_norm(df)
    if entry=="next_open":
        if "open" not in x: raise ValueError("open column required")
        ep=x.groupby("code")["open"].shift(-1)
        xp=x.groupby("code")["close"].shift(-horizon)
    elif entry=="close":
        ep=x[price_col]; xp=x.groupby("code")[price_col].shift(-horizon)
    else: raise ValueError(f"unsupported entry: {entry}")
    r=(xp/ep-1).replace([np.inf,-np.inf],np.nan)
    return pd.Series(r.to_numpy(), index=df.index, name=f"forward_return_{horizon}")

def add_forward_returns(df, horizons: Iterable[int]=(1,5,10,20), entry="next_open"):
    out=df.copy()
    for h in horizons: out[f"forward_return_{h}d"]=calculate_forward_returns(df,h,entry).to_numpy()
    return out

def calculate_daily_returns(equity):
    return pd.Series(equity).astype(float).pct_change().fillna(0.0)

def calculate_cumulative_return(daily_returns):
    return float((1+pd.Series(daily_returns).fillna(0)).prod()-1)

def calculate_max_drawdown(equity):
    e=pd.Series(equity).astype(float)
    if e.empty: return 0.0
    return float((e/e.cummax()-1).min())

def calculate_sharpe(daily_returns, annualization=252):
    r=pd.Series(daily_returns).dropna().astype(float)
    s=r.std(ddof=1)
    return 0.0 if len(r)<2 or s==0 else float(np.sqrt(annualization)*r.mean()/s)
