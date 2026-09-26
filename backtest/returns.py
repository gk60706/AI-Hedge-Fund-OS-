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


# ============================================================================
# V3.9.2 Backtest Returns Engine
# ============================================================================

from dataclasses import dataclass
from typing import Optional


@dataclass
class ForwardReturnConfigV392:
    """
    Forward Return 配置。

    signal_price:
        信号产生时参考价格。
        常见：
        - close

    entry_price:
        下一交易日成交价格。
        常见：
        - open
        - close

    exit_price:
        持有结束后的价格。
        常见：
        - close
        - open

    horizon:
        持有多少个交易日。

    Examples
    --------
    1日 forward return:

        t close
          ↓
        t+1 open
          ↓
        t+1 close

    对应：

        entry = t+1 open
        exit  = t+1 close

    """
    signal_price: str = "close"
    entry_price: str = "open"
    exit_price: str = "close"
    horizon: int = 1
    # 是否允许使用同一天 entry
    allow_same_day_entry: bool = False
    # 缺失价格是否删除
    drop_missing: bool = True
    # 是否要求 entry/exit 都为正数
    require_positive_price: bool = True


@dataclass
class ForwardReturnResultV392:
    """
    Forward Return 计算结果。
    """
    data: pd.DataFrame
    horizon: int
    signal_price: str
    entry_price: str
    exit_price: str
    n_rows: int
    n_valid: int
    n_missing: int
    mean_return: float
    median_return: float
    std_return: float
    min_return: float
    max_return: float


class ForwardReturnEngineV392:
    """
    Forward Return Engine。

    输入：

        date
        code
        open
        high
        low
        close
        signal

    输出：

        entry_date
        entry_price_value
        exit_date
        exit_price_value
        forward_return
    """
    REQUIRED_COLUMNS = {
        "date",
        "code",
    }
    PRICE_COLUMNS = {
        "open",
        "high",
        "low",
        "close",
    }

    def __init__(
        self,
        config: Optional[ForwardReturnConfigV392] = None,
    ):
        self.config = config or ForwardReturnConfigV392()
        if self.config.horizon <= 0:
            raise ValueError("horizon must be >= 1")

    # ========================================================
    # Validation
    # ========================================================
    def validate_input(
        self,
        df: pd.DataFrame,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("df must be pandas.DataFrame")
        missing = (
            self.REQUIRED_COLUMNS - set(df.columns)
        )
        if missing:
            raise ValueError(
                f"Missing required columns: {sorted(missing)}"
            )
        required_prices = {
            self.config.entry_price,
            self.config.exit_price,
        }
        missing_prices = (
            required_prices - set(df.columns)
        )
        if missing_prices:
            raise ValueError(
                f"Missing price columns: {sorted(missing_prices)}"
            )

    # ========================================================
    # Prepare
    # ========================================================
    @staticmethod
    def prepare(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        data = df.copy()
        data["date"] = pd.to_datetime(
            data["date"],
            errors="coerce",
        )
        if data["date"].isna().any():
            raise ValueError("Found invalid date values.")
        data["code"] = (
            data["code"].astype(str).str.strip()
        )
        data = (
            data.sort_values(["code", "date"])
            .reset_index(drop=True)
        )
        duplicates = data.duplicated(
            subset=[
                "date",
                "code",
            ],
            keep=False,
        )
        if duplicates.any():
            duplicated_rows = int(duplicates.sum())
            raise ValueError(
                "Duplicate date+code rows detected: "
                f"{duplicated_rows}"
            )
        return data

    # ========================================================
    # Build future prices
    # ========================================================
    def _shift_price(
        self,
        data: pd.DataFrame,
        column: str,
        periods: int,
    ) -> pd.Series:
        return (
            data.groupby(
                "code",
                group_keys=False,
            )[column].shift(periods)
        )

    # ========================================================
    # Calculate
    # ========================================================
    def calculate(
        self,
        df: pd.DataFrame,
    ) -> ForwardReturnResultV392:
        self.validate_input(df)
        data = self.prepare(df)
        horizon = self.config.horizon
        # ----------------------------------------------------
        # 默认：
        #
        # t 日收盘产生 Alpha
        # t+1 日开盘进入
        # t+h 日收盘退出
        #
        # 因此：
        #
        # entry = shift(-1)
        # exit  = shift(-(horizon))
        #
        # 对 horizon=1：
        #
        # entry = t+1 open
        # exit  = t+1 close
        # ----------------------------------------------------
        entry_shift = 1
        if self.config.allow_same_day_entry:
            entry_shift = 0
        exit_shift = horizon
        data["entry_date"] = (
            data.groupby("code")["date"].shift(
                -entry_shift
            )
        )
        data["exit_date"] = (
            data.groupby("code")["date"].shift(
                -exit_shift
            )
        )
        data["entry_price_value"] = (
            self._shift_price(
                data,
                self.config.entry_price,
                -entry_shift,
            )
        )
        data["exit_price_value"] = (
            self._shift_price(
                data,
                self.config.exit_price,
                -exit_shift,
            )
        )
        # ----------------------------------------------------
        # Return
        # ----------------------------------------------------
        entry = data["entry_price_value"]
        exit_ = data["exit_price_value"]
        data["forward_return"] = (
            exit_ / entry - 1.0
        )
        # ----------------------------------------------------
        # Validity
        # ----------------------------------------------------
        valid = (
            data["entry_price_value"].notna()
            & data["exit_price_value"].notna()
            & data["entry_date"].notna()
            & data["exit_date"].notna()
        )
        if self.config.require_positive_price:
            valid &= (
                data["entry_price_value"] > 0
            )
            valid &= (
                data["exit_price_value"] > 0
            )
        data["forward_return_valid"] = valid
        # ----------------------------------------------------
        # Missing
        # ----------------------------------------------------
        n_rows = len(data)
        n_valid = int(valid.sum())
        n_missing = n_rows - n_valid
        if self.config.drop_missing:
            data = data.loc[valid].copy()
        # ----------------------------------------------------
        # Statistics
        # ----------------------------------------------------
        returns = (
            data["forward_return"]
            .replace(
                [np.inf, -np.inf],
                np.nan,
            )
            .dropna()
        )
        if len(returns) == 0:
            mean_return = np.nan
            median_return = np.nan
            std_return = np.nan
            min_return = np.nan
            max_return = np.nan
        else:
            mean_return = float(returns.mean())
            median_return = float(returns.median())
            std_return = float(
                returns.std(ddof=1)
            ) if len(returns) > 1 else 0.0
            min_return = float(returns.min())
            max_return = float(returns.max())
        return ForwardReturnResultV392(
            data=data,
            horizon=horizon,
            signal_price=self.config.signal_price,
            entry_price=self.config.entry_price,
            exit_price=self.config.exit_price,
            n_rows=n_rows,
            n_valid=n_valid,
            n_missing=n_missing,
            mean_return=mean_return,
            median_return=median_return,
            std_return=std_return,
            min_return=min_return,
            max_return=max_return,
        )


# ============================================================
# Cross Sectional Forward Returns
# ============================================================
def calculate_forward_returns_v392(
    df: pd.DataFrame,
    horizon: int = 1,
    entry_price: str = "open",
    exit_price: str = "close",
    drop_missing: bool = True,
) -> pd.DataFrame:
    """
    简化接口。

    Example
    -------

    result = calculate_forward_returns_v392(
        df,
        horizon=1,
        entry_price="open",
        exit_price="close",
    )

    返回：

        date
        code
        entry_date
        exit_date
        entry_price_value
        exit_price_value
        forward_return
    """
    config = ForwardReturnConfigV392(
        horizon=horizon,
        entry_price=entry_price,
        exit_price=exit_price,
        drop_missing=drop_missing,
    )
    engine = ForwardReturnEngineV392(config)
    result = engine.calculate(df)
    return result.data


# ============================================================
# Multi-Horizon Returns
# ============================================================
def calculate_multi_horizon_returns_v392(
    df: pd.DataFrame,
    horizons: list[int],
    entry_price: str = "open",
    exit_price: str = "close",
) -> pd.DataFrame:
    """
    同时计算多个持有期收益。

    Example
    -------

    horizons = [
        1,
        3,
        5,
        10,
        20,
    ]

    输出：

        forward_return_1d
        forward_return_3d
        forward_return_5d
        forward_return_10d
        forward_return_20d
    """
    if not horizons:
        raise ValueError("horizons cannot be empty")
    data = ForwardReturnEngineV392.prepare(df)
    result = data.copy()
    for horizon in horizons:
        if horizon <= 0:
            raise ValueError("All horizons must be >= 1")
        entry_shift = -1
        exit_shift = -horizon
        entry = (
            data.groupby("code")[entry_price].shift(
                entry_shift
            )
        )
        exit_ = (
            data.groupby("code")[exit_price].shift(
                exit_shift
            )
        )
        result[f"forward_return_{horizon}d"] = (
            exit_ / entry - 1.0
        )
    return result


# ============================================================
# Open-to-Open
# ============================================================
def calculate_open_to_open_return_v392(
    df: pd.DataFrame,
    horizon: int = 1,
) -> pd.DataFrame:
    """
    Open-to-open forward return。

    t+1 open -> t+1+horizon open
    """
    data = ForwardReturnEngineV392.prepare(df)
    entry = (
        data.groupby("code")["open"].shift(-1)
    )
    exit_ = (
        data.groupby("code")["open"].shift(
            -(1 + horizon)
        )
    )
    data["open_to_open_return"] = (
        exit_ / entry - 1.0
    )
    return data


# ============================================================
# Close-to-Close
# ============================================================
def calculate_close_to_close_return_v392(
    df: pd.DataFrame,
    horizon: int = 1,
) -> pd.DataFrame:
    """
    Close-to-close forward return。

    t close -> t+horizon close
    """
    data = ForwardReturnEngineV392.prepare(df)
    entry = data["close"]
    exit_ = (
        data.groupby("code")["close"].shift(
            -horizon
        )
    )
    data["close_to_close_return"] = (
        exit_ / entry - 1.0
    )
    return data


# ============================================================
# Excess Return
# ============================================================
def calculate_excess_return_v392(
    df: pd.DataFrame,
    forward_return_column: str = "forward_return",
    benchmark_column: str = "benchmark_return",
) -> pd.DataFrame:
    """
    计算相对基准的超额收益。

        excess_return
        =
        stock_return - benchmark_return
    """
    data = df.copy()
    if forward_return_column not in data.columns:
        raise ValueError(
            f"Missing column: {forward_return_column}"
        )
    if benchmark_column not in data.columns:
        raise ValueError(
            f"Missing column: {benchmark_column}"
        )
    data["excess_return"] = (
        data[forward_return_column]
        - data[benchmark_column]
    )
    return data


# ============================================================
# Cross-sectional Rank Return
# ============================================================
def calculate_quantile_returns_v392(
    df: pd.DataFrame,
    signal_column: str = "signal",
    return_column: str = "forward_return",
    quantiles: int = 5,
) -> pd.DataFrame:
    """
    根据 Alpha 信号进行横截面分组。

    Q1 = 最低信号组
    Q5 = 最高信号组

    注意：
    这里只负责分组和收益计算，
    不负责判断 Alpha 方向。
    """
    if signal_column not in df.columns:
        raise ValueError(
            f"Missing signal column: {signal_column}"
        )
    if return_column not in df.columns:
        raise ValueError(
            f"Missing return column: {return_column}"
        )
    if quantiles < 2:
        raise ValueError("quantiles must be >= 2")
    data = df.copy()

    def assign_quantile(
        group: pd.DataFrame,
    ) -> pd.Series:
        signal = group[signal_column]
        valid = signal.notna()
        result = pd.Series(
            np.nan,
            index=group.index,
            dtype=float,
        )
        if valid.sum() < quantiles:
            return result
        ranks = signal[valid].rank(method="first")
        result.loc[valid] = (
            pd.qcut(
                ranks,
                q=quantiles,
                labels=False,
            )
            + 1
        )
        return result

    data["signal_quantile"] = (
        data.groupby(
            "date",
            group_keys=False,
        )
        .apply(
            assign_quantile,
            include_groups=False,
        )
        .reindex(data.index)
    )
    return data


# ============================================================
# Long-only Portfolio Return
# ============================================================
def calculate_long_only_quantile_return_v392(
    df: pd.DataFrame,
    signal_column: str = "signal",
    return_column: str = "forward_return",
    quantile: int = 5,
) -> pd.DataFrame:
    """
    计算最高 Alpha 分组的简单平均收益。

    这是研究用途的横截面 long-only return，
    不包含：

    - 交易成本
    - 滑点
    - 涨跌停成交限制
    - 仓位约束
    - 100股整数手
    - 现金管理

    后续由 alpha_backtest.py 处理。
    """
    data = calculate_quantile_returns_v392(
        df,
        signal_column=signal_column,
        return_column=return_column,
        quantiles=quantile,
    )
    selected = (
        data[data["signal_quantile"] == quantile]
        .copy()
    )
    daily = (
        selected.groupby("date")[return_column]
        .mean()
        .rename("long_only_return")
        .reset_index()
    )
    daily["long_only_cumulative"] = (
        1.0 + daily["long_only_return"]
    ).cumprod() - 1.0
    return daily


# ============================================================
# IC Dataset
# ============================================================
def prepare_alpha_dataset_v392(
    df: pd.DataFrame,
    signal_column: str = "signal",
    horizon: int = 1,
) -> pd.DataFrame:
    """
    将原始价格数据转换为 Alpha Research 数据集。

    流程：

        Price Panel
             ↓
        Forward Return
             ↓
        Alpha Dataset

    输出：

        date
        code
        signal
        forward_return
    """
    if signal_column not in df.columns:
        raise ValueError(
            f"Missing signal column: {signal_column}"
        )
    returns = calculate_forward_returns_v392(
        df,
        horizon=horizon,
        entry_price="open",
        exit_price="close",
    )
    columns = [
        "date",
        "code",
        signal_column,
        "forward_return",
    ]
    columns = [
        c for c in columns if c in returns.columns
    ]
    result = returns[columns].copy()
    result = result.dropna(
        subset=[
            signal_column,
            "forward_return",
        ]
    )
    return result


# ============================================================
# Self Test
# ============================================================
def _demo_v392() -> None:
    dates = pd.date_range(
        "2026-01-01",
        periods=10,
        freq="B",
    )
    rows = []
    codes = [
        "000001",
        "000002",
        "000003",
    ]
    for code_idx, code in enumerate(codes):
        for i, date in enumerate(dates):
            base = (
                100 + code_idx * 10 + i
            )
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "open": base,
                    "high": base + 2,
                    "low": base - 2,
                    "close": base + 1,
                    "volume": 1000000,
                    "amount": 100000000,
                }
            )
    df = pd.DataFrame(rows)
    result = calculate_forward_returns_v392(
        df,
        horizon=1,
    )
    print("\nForward Return Demo")
    print(
        result[
            [
                "date",
                "code",
                "entry_date",
                "exit_date",
                "entry_price_value",
                "exit_price_value",
                "forward_return",
            ]
        ].head(10)
    )
    print("\nRows:", len(result))
    multi = calculate_multi_horizon_returns_v392(
        df,
        horizons=[
            1,
            3,
            5,
        ],
    )
    print("\nMulti Horizon:")
    print(
        multi[
            [
                "date",
                "code",
                "forward_return_1d",
                "forward_return_3d",
                "forward_return_5d",
            ]
        ].head()
    )


# ============================================================
# Tests
# ============================================================
def _self_test_v392() -> None:
    dates = pd.date_range(
        "2026-01-01",
        periods=5,
        freq="B",
    )
    df = pd.DataFrame(
        {
            "date": dates,
            "code": ["000001"] * 5,
            "open": [
                10,
                11,
                12,
                13,
                14,
            ],
            "close": [
                10.5,
                11.5,
                12.5,
                13.5,
                14.5,
            ],
        }
    )
    result = calculate_forward_returns_v392(
        df,
        horizon=1,
    )
    assert len(result) == 4
    # t=2026-01-01
    # entry = next open = 11
    # exit = next close = 11.5
    # return = 11.5 / 11 - 1
    expected = (
        11.5 / 11.0 - 1.0
    )
    actual = result.iloc[0]["forward_return"]
    assert np.isclose(actual, expected)
    # --------------------------------------------------------
    # Multi horizon
    # --------------------------------------------------------
    multi = calculate_multi_horizon_returns_v392(
        df,
        horizons=[
            1,
            2,
        ],
    )
    assert (
        "forward_return_1d" in multi.columns
    )
    assert (
        "forward_return_2d" in multi.columns
    )
    # --------------------------------------------------------
    # Close-to-close
    # --------------------------------------------------------
    c2c = calculate_close_to_close_return_v392(
        df,
        horizon=1,
    )
    assert (
        "close_to_close_return" in c2c.columns
    )
    print("backtest/returns.py V392 self-test passed.")


if __name__ == "__main__":
    _self_test_v392()
