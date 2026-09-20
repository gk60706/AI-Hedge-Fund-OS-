from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .costs import TransactionCostModel, build_cost_model
from .returns import calculate_max_drawdown, calculate_sharpe

@dataclass
class BacktestResult:
    alpha_name:str; initial_capital:float; final_capital:float; total_return:float
    annualized_return:float; max_drawdown:float; sharpe:float; turnover:float
    total_cost:float; trading_days:int; equity_curve:pd.DataFrame; daily_records:pd.DataFrame

def _name(a):
    if isinstance(a,str): return a
    for k in ("name","alpha_id","expression"):
        v=getattr(a,k,None)
        if v: return str(v)
    return str(a)

def _eval(a,df):
    if callable(a): y=a(df)
    elif hasattr(a,"evaluate"): y=a.evaluate(df)
    elif isinstance(a,str) and a in df: y=df[a]
    else: raise TypeError("alpha must be callable, evaluatable, or a column name")
    if isinstance(y,pd.DataFrame):
        if y.shape[1]!=1: raise ValueError("alpha returned multiple columns")
        y=y.iloc[:,0]
    return pd.Series(y,index=df.index,dtype=float)

class AlphaBacktester:
    def __init__(self,config=None,cost_config=None,initial_capital=None,portfolio_size=None):
        self.config=config or {}
        self.initial_capital=float(initial_capital if initial_capital is not None else self.config.get("initial_capital",10_000_000))
        self.portfolio_size=int(portfolio_size if portfolio_size is not None else self.config.get("portfolio_size",20))
        self.cost_model=cost_config if isinstance(cost_config,TransactionCostModel) else build_cost_model(cost_config or {})
    @staticmethod
    def _tradable(row,side):
        if not bool(row.get("is_tradeable",True)): return False
        if side=="buy" and bool(row.get("limit_up",False)): return False
        if side=="sell" and bool(row.get("limit_down",False)): return False
        return True
    def run(self,alpha,panel):
        x=panel.copy()
        need={"date","code","open","close"}; miss=need-set(x.columns)
        if miss: raise ValueError(f"missing columns: {sorted(miss)}")
        x["date"]=pd.to_datetime(x["date"]); x["code"]=x["code"].astype(str)
        x=x.sort_values(["date","code"]).reset_index(drop=True)
        x["signal"]=_eval(alpha,x).to_numpy()
        dates=sorted(x.date.unique())
        if len(dates)<2: raise ValueError("at least two dates required")
        equity=self.initial_capital; prev=set(); total_cost=0.; turnover=0.; rec=[]
        for i,d in enumerate(dates[:-1]):
            day=x[x.date==d].dropna(subset=["signal"])
            nxt=x[x.date==dates[i+1]]
            cand=day[day.apply(lambda r:self._tradable(r,"buy"),axis=1)]
            target=set(cand.sort_values("signal",ascending=False).head(self.portfolio_size).code)
            buys=target-prev; sells=prev-target
            n=max(len(target),1); tw=1/n
            bv=sv=0.
            for code in buys:
                r=nxt[nxt.code==code]
                if not r.empty and pd.notna(r.iloc[0].open): bv+=self.initial_capital*tw
            for code in sells:
                r=nxt[nxt.code==code]
                if not r.empty and self._tradable(r.iloc[0],"sell"): sv+=self.initial_capital*tw
            cost=self.cost_model.calculate(bv,sv); total_cost+=cost["total_cost"]; turnover+=cost["turnover_value"]
            prices=nxt[nxt.code.isin(target)][["code","open","close"]].dropna()
            gross=float((prices.close/prices.open-1).mean()) if not prices.empty else 0.
            net=gross-cost["total_cost"]/self.initial_capital
            equity*=1+net
            rec.append({"signal_date":pd.Timestamp(d),"execution_date":pd.Timestamp(dates[i+1]),
                        "n_holdings":len(target),"buy_count":len(buys),"sell_count":len(sells),
                        "turnover_value":cost["turnover_value"],"transaction_cost":cost["total_cost"],
                        "gross_return":gross,"net_return":net,"equity":equity,"holdings":sorted(target)})
            prev=target
        daily=pd.DataFrame(rec)
        if daily.empty: raise ValueError("no tradable observations")
        r=daily.net_return; years=max(len(daily)/252,1/252)
        return BacktestResult(_name(alpha),self.initial_capital,equity,equity/self.initial_capital-1,
            (equity/self.initial_capital)**(1/years)-1,calculate_max_drawdown(daily.equity),
            calculate_sharpe(r),turnover/self.initial_capital,total_cost,len(daily),
            daily[["execution_date","equity"]].copy(),daily)
