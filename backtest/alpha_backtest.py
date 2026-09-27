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


# ============================================================================
# V3.9.2 Alpha Backtest Engine (V392 suffix names)
# ============================================================================

from dataclasses import dataclass, asdict
from typing import Optional
from .returns import calculate_forward_returns_v392
from .costs import TransactionCostConfigV392, calculate_turnover_cost_v392


# ============================================================
# Configuration
# ============================================================
@dataclass
class AlphaBacktestConfigV392:
    """
    Alpha 回测配置。
    """
    # Forward Return
    horizon: int = 1
    entry_price: str = "open"
    exit_price: str = "close"
    # Quantile
    quantiles: int = 5
    # IC
    min_cross_section: int = 10
    # Portfolio
    long_only: bool = True
    # Long-only 使用最高分组
    long_quantile: int = 5
    # 是否计算 Q5-Q1
    calculate_long_short: bool = True
    # 成本
    transaction_cost: TransactionCostConfigV392 = (
        None
    )
    # 是否使用复利净收益
    compounded_net_return: bool = False
    # Sharpe 年化
    annualization: int = 252
    # 是否允许缺失 forward return
    drop_missing_return: bool = True

    def __post_init__(self):
        if self.horizon <= 0:
            raise ValueError(
                "horizon must be >= 1"
            )
        if self.quantiles < 2:
            raise ValueError(
                "quantiles must be >= 2"
            )
        if not (
            1 <= self.long_quantile <= self.quantiles
        ):
            raise ValueError(
                "long_quantile must be "
                "between 1 and quantiles"
            )
        if self.annualization <= 0:
            raise ValueError(
                "annualization must be > 0"
            )
        if self.transaction_cost is None:
            self.transaction_cost = (
                TransactionCostConfigV392()
            )


# ============================================================
# Daily Metrics
# ============================================================
@dataclass
class AlphaDailyMetricsV392:
    """
    每日 Alpha 指标。
    """
    date: pd.Timestamp
    ic: float
    n_stocks: int
    q1_return: float
    q5_return: float
    q5_q1_spread: float
    long_only_return: float
    turnover: float
    transaction_cost: float
    net_return: float


# ============================================================
# Overall Result
# ============================================================
@dataclass
class AlphaBacktestResultV392:
    """
    Alpha 回测完整结果。
    """
    daily: pd.DataFrame
    ic_mean: float
    ic_std: float
    icir: float
    positive_ic_ratio: float
    q5_mean: float
    q1_mean: float
    q5_q1_mean: float
    long_only_mean: float
    average_turnover: float
    total_transaction_cost: float
    gross_return: float
    net_return: float
    cumulative_gross_return: float
    cumulative_net_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    max_drawdown: float
    n_days: int
    n_observations: int
    passed_basic_checks: bool
    metadata: dict


# ============================================================
# Statistics
# ============================================================
def _safe_mean_v392(
    series: pd.Series,
) -> float:
    values = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()
    if len(values) == 0:
        return np.nan
    return float(
        values.mean()
    )


def _safe_std_v392(
    series: pd.Series,
) -> float:
    values = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()
    if len(values) <= 1:
        return np.nan
    return float(
        values.std(ddof=1)
    )


def _safe_ratio_v392(
    numerator: float,
    denominator: float,
) -> float:
    if not np.isfinite(numerator):
        return np.nan
    if not np.isfinite(denominator):
        return np.nan
    if denominator == 0:
        return np.nan
    return float(
        numerator / denominator
    )


# ============================================================
# IC
# ============================================================
def calculate_daily_ic_v392(
    group: pd.DataFrame,
    signal_column: str,
    return_column: str,
    min_cross_section: int = 10,
) -> float:
    """
    计算单日横截面 Spearman Rank IC。

    Alpha Research 中：

        IC_t
        =
        corr(
            rank(signal_t),
            rank(return_t)
        )
    """
    data = group[
        [
            signal_column,
            return_column,
        ]
    ].copy()
    data = data.replace(
        [
            np.inf,
            -np.inf,
        ],
        np.nan,
    ).dropna()
    if len(data) < min_cross_section:
        return np.nan
    if (
        data[signal_column].nunique() < 2
    ):
        return np.nan
    if (
        data[return_column].nunique() < 2
    ):
        return np.nan
    ic = data[signal_column].corr(
        data[return_column],
        method="spearman",
    )
    if pd.isna(ic):
        return np.nan
    return float(ic)


# ============================================================
# Quantile Return
# ============================================================
def _assign_quantiles_v392(
    group: pd.DataFrame,
    signal_column: str,
    quantiles: int,
) -> pd.Series:
    signal = group[signal_column]
    result = pd.Series(
        np.nan,
        index=group.index,
        dtype=float,
    )
    valid = signal.notna()
    if valid.sum() < quantiles:
        return result
    ranks = signal[valid].rank(
        method="first"
    )
    try:
        q = pd.qcut(
            ranks,
            q=quantiles,
            labels=False,
        )
        result.loc[valid] = q + 1
    except ValueError:
        return result
    return result


def add_signal_quantiles_v392(
    df: pd.DataFrame,
    signal_column: str = "signal",
    quantiles: int = 5,
) -> pd.DataFrame:
    """
    为每个交易日进行横截面分组。

    Q1 = 最低 Alpha
    Q5 = 最高 Alpha
    """
    data = df.copy()
    data["signal_quantile"] = (
        data.groupby(
            "date",
            group_keys=False,
        ).apply(
            lambda x: _assign_quantiles_v392(
                x,
                signal_column,
                quantiles,
            ),
            include_groups=False,
        ).reindex(
            data.index
        )
    )
    return data


# ============================================================
# Quantile Daily Return
# ============================================================
def calculate_daily_quantile_returns_v392(
    group: pd.DataFrame,
    return_column: str,
    quantiles: int,
) -> dict:
    """
    计算单日 Q1/Q5/Long-only 收益。
    """
    result = {}
    q_returns = {}
    for q in range(
        1,
        quantiles + 1,
    ):
        values = group.loc[
            group["signal_quantile"] == q,
            return_column,
        ]
        if len(values) == 0:
            q_returns[q] = np.nan
        else:
            q_returns[q] = float(
                values.mean()
            )
    result["q1_return"] = (
        q_returns.get(
            1,
            np.nan,
        )
    )
    result["q5_return"] = (
        q_returns.get(
            quantiles,
            np.nan,
        )
    )
    result["q5_q1_spread"] = (
        result["q5_return"] - result["q1_return"]
    )
    result["long_only_return"] = (
        result["q5_return"]
    )
    return result


# ============================================================
# Turnover
# ============================================================
def calculate_daily_turnover_v392(
    previous_codes: set[str],
    current_codes: set[str],
) -> float:
    """
    使用股票代码计算组合换手。

    注意：
    不能使用 DataFrame index。

    因为不同日期的 DataFrame index
    不代表同一只股票。

    简单集合换手定义：

        turnover =
            1 - intersection / current

    这是研究级近似。

    后续 Portfolio Engine 会进一步升级
    为权重变化：

        0.5 * Sum |w_t - w_{t-1}|
    """
    if not current_codes:
        return np.nan
    if not previous_codes:
        return 1.0
    intersection = (
        previous_codes & current_codes
    )
    return float(
        1.0
        - (
            len(intersection) / len(current_codes)
        )
    )


# ============================================================
# Equity Curve
# ============================================================
def calculate_equity_curve_v392(
    returns: pd.Series,
) -> pd.Series:
    """
    根据日收益计算净值。
    """
    clean = pd.to_numeric(
        returns,
        errors="coerce",
    ).fillna(0.0)
    return (
        1.0 + clean
    ).cumprod()


def calculate_max_drawdown_v392(
    equity: pd.Series,
) -> float:
    """
    最大回撤。

        Drawdown =
            Equity / RunningMax - 1
    """
    equity = pd.to_numeric(
        equity,
        errors="coerce",
    ).dropna()
    if len(equity) == 0:
        return np.nan
    running_max = equity.cummax()
    drawdown = (
        equity / running_max - 1.0
    )
    return float(
        drawdown.min()
    )


# ============================================================
# Sharpe
# ============================================================
def calculate_sharpe_v392(
    returns: pd.Series,
    annualization: int = 252,
) -> float:
    values = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()
    if len(values) <= 1:
        return np.nan
    std = values.std(ddof=1)
    if std == 0 or pd.isna(std):
        return np.nan
    return float(
        values.mean() / std * np.sqrt(annualization)
    )


# ============================================================
# Annualized Return
# ============================================================
def calculate_annualized_return_v392(
    returns: pd.Series,
    annualization: int = 252,
) -> float:
    values = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()
    if len(values) == 0:
        return np.nan
    cumulative = (
        1.0 + values
    ).prod()
    if cumulative <= 0:
        return np.nan
    years = (
        len(values) / annualization
    )
    if years <= 0:
        return np.nan
    return float(
        cumulative ** (1.0 / years) - 1.0
    )


def calculate_annualized_volatility_v392(
    returns: pd.Series,
    annualization: int = 252,
) -> float:
    values = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()
    if len(values) <= 1:
        return np.nan
    return float(
        values.std(ddof=1) * np.sqrt(annualization)
    )


# ============================================================
# Main Engine
# ============================================================
class AlphaBacktestEngineV392:
    """
    Alpha Backtest Engine。
    """
    REQUIRED_COLUMNS = {
        "date",
        "code",
        "signal",
    }

    def __init__(
        self,
        config: Optional[AlphaBacktestConfigV392] = None,
    ):
        self.config = (
            config or AlphaBacktestConfigV392()
        )

    # ========================================================
    # Validation
    # ========================================================
    def validate_input(
        self,
        df: pd.DataFrame,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                "df must be pandas.DataFrame"
            )
        missing = (
            self.REQUIRED_COLUMNS - set(df.columns)
        )
        if missing:
            raise ValueError(
                "Missing required columns: "
                f"{sorted(missing)}"
            )
        price_columns = {
            self.config.entry_price,
            self.config.exit_price,
        }
        missing_prices = (
            price_columns - set(df.columns)
        )
        if missing_prices:
            raise ValueError(
                "Missing price columns: "
                f"{sorted(missing_prices)}"
            )

    # ========================================================
    # Prepare
    # ========================================================
    def prepare(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        self.validate_input(df)
        data = df.copy()
        data["date"] = pd.to_datetime(
            data["date"],
            errors="coerce",
        )
        if data["date"].isna().any():
            raise ValueError(
                "Invalid date values detected."
            )
        data["code"] = (
            data["code"].astype(str).str.strip()
        )
        data["signal"] = pd.to_numeric(
            data["signal"],
            errors="coerce",
        )
        data = data.sort_values(
            [
                "date",
                "code",
            ]
        ).reset_index(
            drop=True
        )
        duplicates = data.duplicated(
            subset=[
                "date",
                "code",
            ],
            keep=False,
        )
        if duplicates.any():
            raise ValueError(
                "Duplicate date+code rows "
                "detected."
            )
        return data

    # ========================================================
    # Forward Return
    # ========================================================
    def add_forward_returns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        returns = calculate_forward_returns_v392(
            df,
            horizon=self.config.horizon,
            entry_price=self.config.entry_price,
            exit_price=self.config.exit_price,
            drop_missing=False,
        )
        columns = [
            "date",
            "code",
            "entry_date",
            "exit_date",
            "entry_price_value",
            "exit_price_value",
            "forward_return",
        ]
        columns = [
            c for c in columns if c in returns.columns
        ]
        return returns[columns].copy()

    # ========================================================
    # Merge Signal + Return
    # ========================================================
    def build_research_dataset(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        data = self.prepare(df)
        returns = self.add_forward_returns(data)
        merged = data.merge(
            returns,
            on=[
                "date",
                "code",
            ],
            how="left",
            suffixes=(
                "",
                "_return",
            ),
        )
        merged = merged.sort_values(
            [
                "date",
                "code",
            ]
        ).reset_index(
            drop=True
        )
        if self.config.drop_missing_return:
            merged = merged[
                merged["forward_return"].notna()
            ].copy()
        return merged

    # ========================================================
    # Daily Evaluation
    # ========================================================
    def evaluate_daily(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        data = add_signal_quantiles_v392(
            data,
            signal_column="signal",
            quantiles=self.config.quantiles,
        )
        rows = []
        previous_codes: set[str] = set()
        for date, group in data.groupby(
            "date",
            sort=True,
        ):
            group = group.copy()
            ic = calculate_daily_ic_v392(
                group,
                signal_column="signal",
                return_column="forward_return",
                min_cross_section=(
                    self.config.min_cross_section
                ),
            )
            n_stocks = int(
                group["code"].nunique()
            )
            q_metrics = (
                calculate_daily_quantile_returns_v392(
                    group,
                    return_column="forward_return",
                    quantiles=self.config.quantiles,
                )
            )
            current_codes = set(
                group.loc[
                    group["signal_quantile"] == self.config.long_quantile,
                    "code",
                ].astype(str)
            )
            turnover = (
                calculate_daily_turnover_v392(
                    previous_codes,
                    current_codes,
                )
            )
            previous_codes = (
                current_codes
            )
            rows.append(
                {
                    "date": date,
                    "ic": ic,
                    "n_stocks": n_stocks,
                    "q1_return": q_metrics["q1_return"],
                    "q5_return": q_metrics["q5_return"],
                    "q5_q1_spread": q_metrics["q5_q1_spread"],
                    "long_only_return": q_metrics["long_only_return"],
                    "turnover": turnover,
                }
            )
        daily = pd.DataFrame(rows)
        if daily.empty:
            return daily
        # ----------------------------------------------------
        # Transaction Cost
        # ----------------------------------------------------
        turnover_cost = (
            calculate_turnover_cost_v392(
                daily["turnover"],
                config=(
                    self.config.transaction_cost
                ),
            )
        )
        daily["transaction_cost"] = (
            turnover_cost["total_cost"].values
        )
        # ----------------------------------------------------
        # Net Return
        # ----------------------------------------------------
        daily["gross_return"] = daily["long_only_return"]
        daily["net_return"] = (
            daily["gross_return"] - daily["transaction_cost"]
        )
        return daily

    # ========================================================
    # Summary
    # ========================================================
    def summarize(
        self,
        daily: pd.DataFrame,
        n_observations: int,
    ) -> AlphaBacktestResultV392:
        if daily.empty:
            return AlphaBacktestResultV392(
                daily=daily,
                ic_mean=np.nan,
                ic_std=np.nan,
                icir=np.nan,
                positive_ic_ratio=np.nan,
                q5_mean=np.nan,
                q1_mean=np.nan,
                q5_q1_mean=np.nan,
                long_only_mean=np.nan,
                average_turnover=np.nan,
                total_transaction_cost=np.nan,
                gross_return=np.nan,
                net_return=np.nan,
                cumulative_gross_return=np.nan,
                cumulative_net_return=np.nan,
                annualized_return=np.nan,
                annualized_volatility=np.nan,
                sharpe=np.nan,
                max_drawdown=np.nan,
                n_days=0,
                n_observations=n_observations,
                passed_basic_checks=False,
                metadata={},
            )
        # ----------------------------------------------------
        # IC
        # ----------------------------------------------------
        ic = daily["ic"].dropna()
        ic_mean = (
            float(ic.mean())
            if len(ic)
            else np.nan
        )
        ic_std = (
            float(ic.std(ddof=1))
            if len(ic) > 1
            else np.nan
        )
        icir = _safe_ratio_v392(
            ic_mean,
            ic_std,
        )
        positive_ic_ratio = (
            float(
                (ic > 0).mean()
            )
            if len(ic)
            else np.nan
        )
        # ----------------------------------------------------
        # Returns
        # ----------------------------------------------------
        q5_mean = _safe_mean_v392(
            daily["q5_return"]
        )
        q1_mean = _safe_mean_v392(
            daily["q1_return"]
        )
        q5_q1_mean = _safe_mean_v392(
            daily["q5_q1_spread"]
        )
        long_only_mean = _safe_mean_v392(
            daily["long_only_return"]
        )
        # ----------------------------------------------------
        # Turnover / Cost
        # ----------------------------------------------------
        average_turnover = _safe_mean_v392(
            daily["turnover"]
        )
        total_transaction_cost = float(
            daily["transaction_cost"].fillna(0.0).sum()
        )
        # ----------------------------------------------------
        # Gross
        # ----------------------------------------------------
        gross_returns = (
            daily["gross_return"].fillna(0.0)
        )
        net_returns = (
            daily["net_return"].fillna(0.0)
        )
        gross_equity = (
            calculate_equity_curve_v392(
                gross_returns
            )
        )
        net_equity = (
            calculate_equity_curve_v392(
                net_returns
            )
        )
        cumulative_gross_return = (
            float(
                gross_equity.iloc[-1] - 1.0
            )
        )
        cumulative_net_return = (
            float(
                net_equity.iloc[-1] - 1.0
            )
        )
        # ----------------------------------------------------
        # Annualized
        # ----------------------------------------------------
        annualized_return = (
            calculate_annualized_return_v392(
                net_returns,
                self.config.annualization,
            )
        )
        annualized_volatility = (
            calculate_annualized_volatility_v392(
                net_returns,
                self.config.annualization,
            )
        )
        sharpe = calculate_sharpe_v392(
            net_returns,
            self.config.annualization,
        )
        max_drawdown = (
            calculate_max_drawdown_v392(
                net_equity
            )
        )
        # ----------------------------------------------------
        # Basic Checks
        # ----------------------------------------------------
        passed_basic_checks = True
        if n_observations <= 0:
            passed_basic_checks = False
        if len(ic) == 0:
            passed_basic_checks = False
        if len(daily) == 0:
            passed_basic_checks = False
        metadata = {
            "config": asdict(self.config),
            "research_type": (
                "cross_sectional_alpha"
            ),
            "return_definition": (
                f"{self.config.entry_price}"
                f"(t+1) -> "
                f"{self.config.exit_price}"
                f"(t+{self.config.horizon})"
            ),
        }
        return AlphaBacktestResultV392(
            daily=daily,
            ic_mean=ic_mean,
            ic_std=ic_std,
            icir=icir,
            positive_ic_ratio=(
                positive_ic_ratio
            ),
            q5_mean=q5_mean,
            q1_mean=q1_mean,
            q5_q1_mean=q5_q1_mean,
            long_only_mean=long_only_mean,
            average_turnover=(
                average_turnover
            ),
            total_transaction_cost=(
                total_transaction_cost
            ),
            gross_return=float(
                gross_returns.mean()
            ),
            net_return=float(
                net_returns.mean()
            ),
            cumulative_gross_return=(
                cumulative_gross_return
            ),
            cumulative_net_return=(
                cumulative_net_return
            ),
            annualized_return=(
                annualized_return
            ),
            annualized_volatility=(
                annualized_volatility
            ),
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            n_days=len(daily),
            n_observations=(
                n_observations
            ),
            passed_basic_checks=(
                passed_basic_checks
            ),
            metadata=metadata,
        )

    # ========================================================
    # Run
    # ========================================================
    def run(
        self,
        df: pd.DataFrame,
    ) -> AlphaBacktestResultV392:
        research = (
            self.build_research_dataset(df)
        )
        n_observations = len(research)
        daily = self.evaluate_daily(research)
        return self.summarize(
            daily,
            n_observations,
        )


# ============================================================
# Convenience API
# ============================================================
def run_alpha_backtest_v392(
    df: pd.DataFrame,
    config: Optional[AlphaBacktestConfigV392] = None,
) -> AlphaBacktestResultV392:
    """
    运行 Alpha 回测。

    Example
    -------

    result = run_alpha_backtest_v392(
        data,
        AlphaBacktestConfigV392(
            horizon=1,
            quantiles=5,
        ),
    )

    """
    engine = AlphaBacktestEngineV392(
        config
    )
    return engine.run(
        df
    )


# ============================================================
# Result To Dict
# ============================================================
def alpha_result_to_dict_v392(
    result: AlphaBacktestResultV392,
) -> dict:
    return {
        "ic_mean": result.ic_mean,
        "ic_std": result.ic_std,
        "icir": result.icir,
        "positive_ic_ratio": (
            result.positive_ic_ratio
        ),
        "q5_mean": result.q5_mean,
        "q1_mean": result.q1_mean,
        "q5_q1_mean": result.q5_q1_mean,
        "long_only_mean": (
            result.long_only_mean
        ),
        "average_turnover": (
            result.average_turnover
        ),
        "total_transaction_cost": (
            result.total_transaction_cost
        ),
        "gross_return": result.gross_return,
        "net_return": result.net_return,
        "cumulative_gross_return": (
            result.cumulative_gross_return
        ),
        "cumulative_net_return": (
            result.cumulative_net_return
        ),
        "annualized_return": (
            result.annualized_return
        ),
        "annualized_volatility": (
            result.annualized_volatility
        ),
        "sharpe": result.sharpe,
        "max_drawdown": (
            result.max_drawdown
        ),
        "n_days": result.n_days,
        "n_observations": (
            result.n_observations
        ),
        "passed_basic_checks": (
            result.passed_basic_checks
        ),
        "metadata": result.metadata,
    }


# ============================================================
# Demo
# ============================================================
def _demo_v392() -> None:
    rng = np.random.default_rng(42)
    dates = pd.date_range(
        "2024-01-01",
        periods=120,
        freq="B",
    )
    codes = [
        f"{i:06d}"
        for i in range(1, 101)
    ]
    rows = []
    for date in dates:
        for code in codes:
            signal = rng.normal()
            # 模拟一个隐藏 Alpha
            future_component = (
                signal * 0.01
            )
            open_price = (
                10.0 + rng.normal(0, 0.2)
            )
            close_price = (
                open_price
                * (
                    1.0
                    + future_component
                    + rng.normal(0, 0.02)
                )
            )
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "open": max(
                        0.1,
                        open_price,
                    ),
                    "close": max(
                        0.1,
                        close_price,
                    ),
                    "signal": signal,
                }
            )
    df = pd.DataFrame(rows)
    config = AlphaBacktestConfigV392(
        horizon=1,
        quantiles=5,
        min_cross_section=30,
    )
    result = run_alpha_backtest_v392(
        df,
        config,
    )
    print()
    print("========================================")
    print("V3.9.2 Alpha Backtest Demo")
    print("========================================")
    print(
        f"IC Mean       : {result.ic_mean:.6f}"
    )
    print(
        f"ICIR          : {result.icir:.6f}"
    )
    print(
        f"Positive IC   : {result.positive_ic_ratio:.2%}"
    )
    print(
        f"Q5 Return     : {result.q5_mean:.4%}"
    )
    print(
        f"Q1 Return     : {result.q1_mean:.4%}"
    )
    print(
        f"Q5-Q1         : {result.q5_q1_mean:.4%}"
    )
    print(
        f"Turnover      : {result.average_turnover:.2%}"
    )
    print(
        f"Cost          : {result.total_transaction_cost:.4%}"
    )
    print(
        f"Net Return    : {result.net_return:.4%}"
    )
    print(
        f"Sharpe        : {result.sharpe:.4f}"
    )
    print(
        f"Max Drawdown  : {result.max_drawdown:.2%}"
    )
    print("========================================")


# ============================================================
# Self Test
# ============================================================
def _self_test_v392() -> None:
    rng = np.random.default_rng(123)
    dates = pd.date_range(
        "2026-01-01",
        periods=20,
        freq="B",
    )
    codes = [
        f"{i:06d}"
        for i in range(1, 21)
    ]
    rows = []
    for date in dates:
        for i, code in enumerate(codes):
            signal = float(i)
            open_price = 10.0 + i * 0.1
            # 高 signal 对应更高未来收益
            close_price = (
                open_price
                * (
                    1.0
                    + signal * 0.001
                    + rng.normal(0, 0.002)
                )
            )
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "open": open_price,
                    "close": close_price,
                    "signal": signal,
                }
            )
    df = pd.DataFrame(rows)
    config = AlphaBacktestConfigV392(
        horizon=1,
        quantiles=5,
        min_cross_section=10,
    )
    result = run_alpha_backtest_v392(
        df,
        config,
    )
    # --------------------------------------------------------
    # Basic
    # --------------------------------------------------------
    assert result.n_days > 0
    assert result.n_observations > 0
    assert np.isfinite(
        result.ic_mean
    )
    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------
    assert (
        result.ic_mean > 0
    )
    assert (
        result.q5_q1_mean > 0
    )
    # --------------------------------------------------------
    # Risk metrics
    # --------------------------------------------------------
    assert np.isfinite(
        result.sharpe
    )
    assert (
        result.max_drawdown <= 0
    )
    # --------------------------------------------------------
    # Daily columns
    # --------------------------------------------------------
    required_daily = {
        "date",
        "ic",
        "q1_return",
        "q5_return",
        "q5_q1_spread",
        "long_only_return",
        "turnover",
        "transaction_cost",
        "gross_return",
        "net_return",
    }
    assert required_daily.issubset(
        result.daily.columns
    )
    print(
        "backtest/alpha_backtest.py "
        "V392 self-test passed."
    )


if __name__ == "__main__":
    _self_test_v392()
