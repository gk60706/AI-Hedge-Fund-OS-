"""V3.9.2 Technical Factor Library (step12 factors/technical.py).

技术因子模块。

设计原则：
1. 所有技术指标只能使用当前时点及历史数据。
2. 因子按照 code 分组计算，避免股票之间的数据污染。
3. 因子计算与后续截面标准化/中性化分离。
4. 技术因子本身不负责未来收益计算。
5. 技术因子本身不负责交易执行。
6. 支持直接接入 BaseFactorV392 / FactorResultV392。
7. 尽量避免 pandas groupby.apply 带来的索引对齐问题。

支持因子：
- Momentum 5/20/60/120
- Reversal 5/20
- Volatility 20/60
- ATR 14
- RSI 14
- MA Deviation 5/20/60
- Volume Ratio 5/20
- Amount Ratio 5/20
- Turnover Mean 20
- Breakout 20/60
- Drawdown 20/60
- High-Low Range
- Close Location
- Price Volume Trend (PVT)

注意：技术因子的价格数据依赖复权方式。
AkShareClientV392 默认使用 qfq，那么 momentum / MA deviation / RSI 等价格类因子
将基于前复权价格计算。这对于研究是合理的，但必须在 Experiment Registry 中记录
数据版本和复权方式。
"""

from abc import ABC
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
)

import numpy as np
import pandas as pd

from .base import (
    BaseFactorV392,
    FactorConfigV392,
    FactorContextV392,
    FactorDirectionV392,
    FactorScopeV392,
)


# ============================================================
# Exceptions
# ============================================================
class TechnicalFactorErrorV392(Exception):
    """技术因子基础异常。"""


class TechnicalFactorInputErrorV392(TechnicalFactorErrorV392):
    """技术因子输入数据错误。"""


# ============================================================
# Utility functions
# ============================================================
def _validate_panel_columns_v392(
    data: pd.DataFrame,
    required_columns: Sequence[str],
) -> None:
    """检查输入数据字段。"""
    missing = [
        col for col in required_columns if col not in data.columns
    ]
    if missing:
        raise TechnicalFactorInputErrorV392(
            f"Missing required columns: {missing}"
        )


def _numeric_v392(
    data: pd.DataFrame,
    columns: Sequence[str],
) -> pd.DataFrame:
    """将指定字段转换为数值。"""
    result = data.copy()
    for col in columns:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")
    return result


def _prepare_sorted_v392(
    data: pd.DataFrame,
    numeric_columns: Sequence[str],
) -> pd.DataFrame:
    """准备技术因子计算数据。

    关键：
    - 保留原始行位置
    - 按 code/date 排序
    - reset index
    - 后续恢复原始顺序

    使用原始 position 而不是 DataFrame index，
    可以处理重复 index 的输入数据。
    """
    if not isinstance(data, pd.DataFrame):
        raise TechnicalFactorInputErrorV392("data must be pandas.DataFrame")
    if data.empty:
        result = data.copy()
        result["_original_position"] = np.arange(len(result))
        return result
    result = data.copy()
    result["_original_position"] = np.arange(
        len(result), dtype=np.int64
    )
    result["code"] = result["code"].astype(str)
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    if result["date"].isna().any():
        raise TechnicalFactorInputErrorV392("date contains invalid values.")
    result = _numeric_v392(result, numeric_columns)
    result = (
        result.sort_values(
            ["code", "date", "_original_position"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )
    return result


def _restore_original_order_v392(
    sorted_data: pd.DataFrame,
    values: pd.Series | np.ndarray,
    original_index: pd.Index,
) -> pd.Series:
    """将排序后的计算结果恢复到原始 DataFrame 顺序。"""
    if isinstance(values, pd.Series):
        arr = values.to_numpy()
    else:
        arr = np.asarray(values)
    if len(arr) != len(sorted_data):
        raise TechnicalFactorErrorV392(
            "Result length does not match sorted data length."
        )
    output = np.full(len(sorted_data), np.nan, dtype=float)
    positions = sorted_data["_original_position"].to_numpy(dtype=np.int64)
    output[positions] = arr
    return pd.Series(output, index=original_index, dtype=float)


def _group_shift_v392(
    data: pd.DataFrame,
    column: str,
    periods: int = 1,
) -> pd.Series:
    """按股票分组 shift。"""
    return data.groupby("code", sort=False)[column].shift(periods)


def _group_rolling_mean_v392(
    data: pd.DataFrame,
    column: str,
    window: int,
    min_periods: Optional[int] = None,
) -> pd.Series:
    """按股票计算 rolling mean。"""
    if min_periods is None:
        min_periods = window
    return (
        data.groupby("code", sort=False)[column].transform(
            lambda s: s.rolling(
                window=window, min_periods=min_periods
            ).mean()
        )
    )


def _group_rolling_std_v392(
    data: pd.DataFrame,
    column: str,
    window: int,
    min_periods: Optional[int] = None,
) -> pd.Series:
    """按股票计算 rolling std。"""
    if min_periods is None:
        min_periods = window
    return (
        data.groupby("code", sort=False)[column].transform(
            lambda s: s.rolling(
                window=window, min_periods=min_periods
            ).std()
        )
    )


def _group_rolling_max_v392(
    data: pd.DataFrame,
    column: str,
    window: int,
    min_periods: Optional[int] = None,
) -> pd.Series:
    """按股票计算 rolling max。"""
    if min_periods is None:
        min_periods = window
    return (
        data.groupby("code", sort=False)[column].transform(
            lambda s: s.rolling(
                window=window, min_periods=min_periods
            ).max()
        )
    )


def _safe_divide_v392(
    numerator: pd.Series,
    denominator: pd.Series,
) -> pd.Series:
    """安全除法。0 分母 / 非有限值统一返回 NaN。"""
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    denominator = denominator.replace(
        [np.inf, -np.inf, 0], np.nan
    )
    result = numerator / denominator
    result = result.replace([np.inf, -np.inf], np.nan)
    return result.astype(float)


# ============================================================
# TechnicalFactor Base
# ============================================================
class TechnicalFactorV392(BaseFactorV392, ABC):
    """技术因子基类。

    所有 TechnicalFactor：
    - 输入必须包含 code/date
    - 默认属于 TECHNICAL scope
    - 因子按照股票时间序列计算
    """

    def __init__(self, config: FactorConfigV392):
        super().__init__(config)

    def _prepare_v392(
        self,
        data: pd.DataFrame,
        numeric_columns: Sequence[str],
    ) -> pd.DataFrame:
        """技术因子统一数据准备。"""
        self.validate_input(data)
        return _prepare_sorted_v392(
            data=data, numeric_columns=numeric_columns
        )

    def _restore_v392(
        self,
        sorted_data: pd.DataFrame,
        values: pd.Series | np.ndarray,
        original_index: pd.Index,
    ) -> pd.Series:
        """恢复原始顺序。"""
        return _restore_original_order_v392(
            sorted_data=sorted_data,
            values=values,
            original_index=original_index,
        )

    @staticmethod
    def _clean_result_v392(result: pd.Series) -> pd.Series:
        """清理无穷值。"""
        return result.replace(
            [np.inf, -np.inf], np.nan
        ).astype(float)


# ============================================================
# Momentum
# ============================================================
class MomentumFactorV392(TechnicalFactorV392):
    """动量因子。

    momentum_n = close / close.shift(n) - 1
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = name or f"momentum_{window}"
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=f"{window}-day price momentum.",
            required_columns=["code", "date", "close"],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=window + 1,
            metadata={
                "family": "momentum",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["close"])
        previous_close = _group_shift_v392(
            work, "close", self.window
        )
        result = _safe_divide_v392(work["close"], previous_close) - 1.0
        result = self._clean_result_v392(result)
        return self._restore_v392(work, result, original_index)


# ============================================================
# Reversal
# ============================================================
class ReversalFactorV392(TechnicalFactorV392):
    """短期反转因子。

    reversal_n = -(close / close.shift(n) - 1)
    """

    def __init__(
        self,
        window: int = 5,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = name or f"reversal_{window}"
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=f"{window}-day short-term reversal.",
            required_columns=["code", "date", "close"],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=window + 1,
            metadata={
                "family": "reversal",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["close"])
        previous_close = _group_shift_v392(
            work, "close", self.window
        )
        momentum = _safe_divide_v392(work["close"], previous_close) - 1.0
        result = -momentum
        result = self._clean_result_v392(result)
        return self._restore_v392(work, result, original_index)


# ============================================================
# Volatility
# ============================================================
class VolatilityFactorV392(TechnicalFactorV392):
    """历史波动率。

    使用日收益率 rolling std。
    annualize=True 时乘以 sqrt(252)。
    """

    def __init__(
        self,
        window: int = 20,
        annualize: bool = False,
        name: Optional[str] = None,
    ):
        if window <= 1:
            raise ValueError("window must be greater than 1.")
        suffix = "annualized" if annualize else "daily"
        factor_name = (
            name or f"volatility_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"{window}-day historical volatility ({suffix})."
            ),
            required_columns=["code", "date", "close"],
            output_column=factor_name,
            lookback=window + 1,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.NEGATIVE,
            higher_is_better=False,
            min_obs=window + 1,
            metadata={
                "family": "volatility",
                "window": window,
                "annualize": annualize,
            },
        )
        super().__init__(config)
        self.window = window
        self.annualize = annualize

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["close"])
        previous_close = _group_shift_v392(work, "close", 1)
        daily_return = (
            _safe_divide_v392(work["close"], previous_close) - 1.0
        )
        volatility = (
            daily_return.groupby(
                work["code"], sort=False
            ).transform(
                lambda s: s.rolling(
                    self.window, min_periods=self.window
                ).std()
            )
        )
        if self.annualize:
            volatility = volatility * np.sqrt(252.0)
        result = self._clean_result_v392(volatility)
        return self._restore_v392(work, result, original_index)


# ============================================================
# ATR
# ============================================================
class ATRFactorV392(TechnicalFactorV392):
    """Average True Range。

    TR = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = rolling mean(TR)
    """

    def __init__(
        self,
        window: int = 14,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = name or f"atr_{window}"
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=f"{window}-day Average True Range.",
            required_columns=[
                "code", "date", "high", "low", "close",
            ],
            output_column=factor_name,
            lookback=window + 1,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.NEGATIVE,
            higher_is_better=False,
            min_obs=window,
            metadata={
                "family": "atr",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(
            data, numeric_columns=["high", "low", "close"]
        )
        previous_close = _group_shift_v392(work, "close", 1)
        tr1 = work["high"] - work["low"]
        tr2 = (work["high"] - previous_close).abs()
        tr3 = (work["low"] - previous_close).abs()
        true_range = pd.concat(
            [tr1, tr2, tr3], axis=1
        ).max(axis=1)
        atr = (
            true_range.groupby(
                work["code"], sort=False
            ).transform(
                lambda s: s.rolling(
                    self.window, min_periods=self.window
                ).mean()
            )
        )
        result = self._clean_result_v392(atr)
        return self._restore_v392(work, result, original_index)


# ============================================================
# RSI
# ============================================================
class RSIFactorV392(TechnicalFactorV392):
    """RSI (Wilder 风格 EMA)。

    gain = max(delta, 0)
    loss = max(-delta, 0)
    avg_gain = EWM(alpha=1/window)
    avg_loss = EWM(alpha=1/window)
    RSI = 100 - 100 / (1 + avg_gain / avg_loss)
    """

    def __init__(
        self,
        window: int = 14,
        name: Optional[str] = None,
    ):
        if window <= 1:
            raise ValueError("window must be greater than 1.")
        factor_name = name or f"rsi_{window}"
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=f"{window}-day Relative Strength Index.",
            required_columns=["code", "date", "close"],
            output_column=factor_name,
            lookback=window + 1,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.NEUTRAL,
            higher_is_better=True,
            min_obs=window + 1,
            metadata={
                "family": "rsi",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["close"])
        previous_close = _group_shift_v392(work, "close", 1)
        delta = work["close"] - previous_close
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = (
            gain.groupby(
                work["code"], sort=False
            ).transform(
                lambda s: s.ewm(
                    alpha=1.0 / self.window,
                    adjust=False,
                    min_periods=self.window,
                ).mean()
            )
        )
        avg_loss = (
            loss.groupby(
                work["code"], sort=False
            ).transform(
                lambda s: s.ewm(
                    alpha=1.0 / self.window,
                    adjust=False,
                    min_periods=self.window,
                ).mean()
            )
        )
        rs = _safe_divide_v392(avg_gain, avg_loss)
        rsi = 100.0 - 100.0 / (1.0 + rs)
        # 全程上涨时 RSI 应接近 100
        rsi = rsi.mask(
            (avg_loss == 0) & (avg_gain > 0), 100.0
        )
        # 全程下跌时 RSI 应接近 0
        rsi = rsi.mask(
            (avg_gain == 0) & (avg_loss > 0), 0.0
        )
        result = self._clean_result_v392(rsi)
        return self._restore_v392(work, result, original_index)


# ============================================================
# Moving Average Deviation
# ============================================================
class MovingAverageDeviationFactorV392(TechnicalFactorV392):
    """均线偏离度。

    ma = rolling mean(close)
    deviation = close / ma - 1
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = (
            name or f"ma_deviation_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"Price deviation from {window}-day moving average."
            ),
            required_columns=["code", "date", "close"],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=window,
            metadata={
                "family": "ma_deviation",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["close"])
        ma = _group_rolling_mean_v392(
            work, "close", self.window
        )
        result = (
            _safe_divide_v392(work["close"], ma) - 1.0
        )
        result = self._clean_result_v392(result)
        return self._restore_v392(work, result, original_index)


# ============================================================
# Volume Ratio
# ============================================================
class VolumeRatioFactorV392(TechnicalFactorV392):
    """成交量比率。

    volume_ratio_n = volume / rolling_mean(volume, n)
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = (
            name or f"volume_ratio_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"Current volume relative to {window}-day average volume."
            ),
            required_columns=["code", "date", "volume"],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.NEUTRAL,
            higher_is_better=True,
            min_obs=window,
            metadata={
                "family": "volume",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["volume"])
        average_volume = (
            work.groupby("code", sort=False)["volume"].transform(
                lambda s: s.rolling(
                    self.window, min_periods=self.window
                ).mean()
            )
        )
        result = _safe_divide_v392(work["volume"], average_volume)
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# Amount Ratio
# ============================================================
class AmountRatioFactorV392(TechnicalFactorV392):
    """成交额比率。

    amount_ratio_n = amount / rolling_mean(amount, n)
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = (
            name or f"amount_ratio_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"Current trading amount relative to {window}-day average."
            ),
            required_columns=["code", "date", "amount"],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.NEUTRAL,
            higher_is_better=True,
            min_obs=window,
            metadata={
                "family": "amount",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["amount"])
        average_amount = (
            work.groupby("code", sort=False)["amount"].transform(
                lambda s: s.rolling(
                    self.window, min_periods=self.window
                ).mean()
            )
        )
        result = _safe_divide_v392(work["amount"], average_amount)
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# Turnover Mean
# ============================================================
class TurnoverMeanFactorV392(TechnicalFactorV392):
    """换手率滚动均值。

    要求输入已经存在 turnover 字段。
    不会根据 amount / market_cap 自行猜测换手率，
    防止错误的数据定义进入 Alpha Engine。
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = (
            name or f"turnover_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"{window}-day average turnover rate."
            ),
            required_columns=["code", "date", "turnover"],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.NEUTRAL,
            higher_is_better=True,
            min_obs=window,
            metadata={
                "family": "turnover",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["turnover"])
        result = (
            work.groupby("code", sort=False)["turnover"].transform(
                lambda s: s.rolling(
                    self.window, min_periods=self.window
                ).mean()
            )
        )
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# Breakout
# ============================================================
class BreakoutFactorV392(TechnicalFactorV392):
    """突破强度。

    breakout_n = close / rolling_max(high, n) - 1
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = (
            name or f"breakout_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"{window}-day price breakout strength."
            ),
            required_columns=[
                "code", "date", "high", "close",
            ],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=window,
            metadata={
                "family": "breakout",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(
            data, numeric_columns=["high", "close"]
        )
        rolling_high = _group_rolling_max_v392(
            work, "high", self.window
        )
        result = (
            _safe_divide_v392(work["close"], rolling_high) - 1.0
        )
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# Drawdown
# ============================================================
class DrawdownFactorV392(TechnicalFactorV392):
    """滚动回撤。

    drawdown_n = close / rolling_max(close, n) - 1
    输出 <= 0。
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = (
            name or f"drawdown_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"{window}-day rolling drawdown."
            ),
            required_columns=["code", "date", "close"],
            output_column=factor_name,
            lookback=window,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=window,
            metadata={
                "family": "drawdown",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(data, numeric_columns=["close"])
        rolling_high = _group_rolling_max_v392(
            work, "close", self.window
        )
        result = (
            _safe_divide_v392(work["close"], rolling_high) - 1.0
        )
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# High-Low Range
# ============================================================
class HighLowRangeFactorV392(TechnicalFactorV392):
    """日内高低波动范围。

    high_low_range = (high - low) / close
    """

    def __init__(self, name: str = "high_low_range"):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Daily high-low range normalized by close."
            ),
            required_columns=[
                "code", "date", "high", "low", "close",
            ],
            output_column=name,
            lookback=1,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.NEGATIVE,
            higher_is_better=False,
            min_obs=1,
            metadata={"family": "range"},
        )
        super().__init__(config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(
            data, numeric_columns=["high", "low", "close"]
        )
        result = _safe_divide_v392(
            work["high"] - work["low"],
            work["close"],
        )
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# Close Location Value
# ============================================================
class CloseLocationFactorV392(TechnicalFactorV392):
    """收盘价在当日振幅中的位置。

    CLV = (close - low) / (high - low)，范围 0~1。
    """

    def __init__(self, name: str = "close_location"):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Close location within daily high-low range."
            ),
            required_columns=[
                "code", "date", "high", "low", "close",
            ],
            output_column=name,
            lookback=1,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            metadata={"family": "price_location"},
        )
        super().__init__(config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(
            data, numeric_columns=["high", "low", "close"]
        )
        denominator = work["high"] - work["low"]
        result = _safe_divide_v392(
            work["close"] - work["low"],
            denominator,
        )
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# Price Volume Trend
# ============================================================
class PriceVolumeTrendFactorV392(TechnicalFactorV392):
    """Price Volume Trend (PVT)。

    PVT_t = PVT_{t-1} + volume_t * (close_t - close_{t-1}) / close_{t-1}
    本实现输出 PVT 的 N 日变化率：pvt_change_n = PVT_t - PVT_{t-n}
    """

    def __init__(
        self,
        window: int = 20,
        name: Optional[str] = None,
    ):
        if window <= 0:
            raise ValueError("window must be positive.")
        factor_name = (
            name or f"pvt_change_{window}"
        )
        config = FactorConfigV392(
            name=factor_name,
            version="3.9.2",
            description=(
                f"{window}-day Price Volume Trend change."
            ),
            required_columns=[
                "code", "date", "close", "volume",
            ],
            output_column=factor_name,
            lookback=window + 1,
            scope=FactorScopeV392.TECHNICAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=window + 1,
            metadata={
                "family": "pvt",
                "window": window,
            },
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_v392(
            data, numeric_columns=["close", "volume"]
        )
        previous_close = _group_shift_v392(work, "close", 1)
        price_return = (
            _safe_divide_v392(work["close"], previous_close) - 1.0
        )
        pvt_increment = work["volume"] * price_return
        pvt = (
            pvt_increment.groupby(
                work["code"], sort=False
            ).cumsum()
        )
        previous_pvt = (
            pvt.groupby(
                work["code"], sort=False
            ).shift(self.window)
        )
        result = pvt - previous_pvt
        return self._restore_v392(
            work,
            self._clean_result_v392(result),
            original_index,
        )


# ============================================================
# Convenience builders
# ============================================================
def build_default_technical_factors_v392() -> List[TechnicalFactorV392]:
    """构建 V3.9.2 默认技术因子库。"""
    factors: List[TechnicalFactorV392] = [
        # Momentum
        MomentumFactorV392(5),
        MomentumFactorV392(20),
        MomentumFactorV392(60),
        MomentumFactorV392(120),
        # Reversal
        ReversalFactorV392(5),
        ReversalFactorV392(20),
        # Volatility
        VolatilityFactorV392(20),
        VolatilityFactorV392(60),
        # ATR
        ATRFactorV392(14),
        # RSI
        RSIFactorV392(14),
        # MA deviation
        MovingAverageDeviationFactorV392(5),
        MovingAverageDeviationFactorV392(20),
        MovingAverageDeviationFactorV392(60),
        # Volume
        VolumeRatioFactorV392(5),
        VolumeRatioFactorV392(20),
        # Amount
        AmountRatioFactorV392(5),
        AmountRatioFactorV392(20),
        # Turnover
        TurnoverMeanFactorV392(20),
        # Breakout
        BreakoutFactorV392(20),
        BreakoutFactorV392(60),
        # Drawdown
        DrawdownFactorV392(20),
        DrawdownFactorV392(60),
        # Daily price structure
        HighLowRangeFactorV392(),
        CloseLocationFactorV392(),
        # PVT
        PriceVolumeTrendFactorV392(20),
    ]
    return factors


def technical_factor_registry_v392() -> Dict[str, TechnicalFactorV392]:
    """返回默认技术因子 Registry。"""
    factors = build_default_technical_factors_v392()
    return {factor.name: factor for factor in factors}


# ============================================================
# Batch computation
# ============================================================
def compute_technical_factors_v392(
    data: pd.DataFrame,
    factors: Optional[Sequence[TechnicalFactorV392]] = None,
    context: Optional[FactorContextV392] = None,
) -> pd.DataFrame:
    """批量计算技术因子，返回原始数据 + 技术因子列。"""
    if factors is None:
        factors = build_default_technical_factors_v392()
    result = data.copy()
    for factor in factors:
        factor_result = factor.run(result, context=context)
        # FactorResultV392.data 是 Series
        result[factor.output_column] = factor_result.data
    return result


# ============================================================
# Technical factor metadata
# ============================================================
def technical_factor_metadata_v392() -> List[Dict[str, Any]]:
    """返回技术因子元数据，供 Experiment Registry / Alpha Search 使用。"""
    factors = build_default_technical_factors_v392()
    return [factor.get_metadata() for factor in factors]


# ============================================================
# Self test
# ============================================================
def _create_test_panel_v392(n_days: int = 80) -> pd.DataFrame:
    """创建测试数据：两只股票 600000 / 000001。"""
    dates = pd.bdate_range("2025-01-01", periods=n_days)
    rows = []
    rng = np.random.default_rng(42)
    for code, base in [
        ("600000", 10.0),
        ("000001", 20.0),
    ]:
        returns = rng.normal(0.001, 0.02, size=n_days)
        closes = base * np.cumprod(1 + returns)
        for i, date in enumerate(dates):
            close = closes[i]
            high = close * (
                1 + abs(rng.normal(0, 0.01))
            )
            low = close * (
                1 - abs(rng.normal(0, 0.01))
            )
            volume = 1_000_000 * (1 + rng.random())
            amount = volume * close
            turnover = rng.random() * 5
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "open": close,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "amount": amount,
                    "turnover": turnover,
                }
            )
    return pd.DataFrame(rows)


def run_self_test_v392() -> None:
    """Technical factor self-test。"""
    panel = _create_test_panel_v392()

    # 1. 基础 Registry
    registry = technical_factor_registry_v392()
    assert "momentum_20" in registry
    assert "rsi_14" in registry
    assert "volatility_20" in registry

    # 2. 单因子测试
    momentum = MomentumFactorV392(20)
    result = momentum.run(panel)
    assert len(result.data) == len(panel)
    assert result.data.index.equals(panel.index)

    # 3. 批量测试
    selected_factors = [
        MomentumFactorV392(20),
        ReversalFactorV392(5),
        VolatilityFactorV392(20),
        ATRFactorV392(14),
        RSIFactorV392(14),
        MovingAverageDeviationFactorV392(20),
        VolumeRatioFactorV392(20),
        AmountRatioFactorV392(20),
        TurnoverMeanFactorV392(20),
        BreakoutFactorV392(20),
        DrawdownFactorV392(20),
        HighLowRangeFactorV392(),
        CloseLocationFactorV392(),
        PriceVolumeTrendFactorV392(20),
    ]
    enriched = compute_technical_factors_v392(
        panel, factors=selected_factors
    )
    for factor in selected_factors:
        assert factor.output_column in enriched.columns

    # 4. No cross-stock contamination
    original = panel.copy()
    factor = MomentumFactorV392(20)
    baseline = factor.run(original).data
    modified = original.copy()
    mask = modified["code"] == "600000"
    modified.loc[mask, "close"] *= 10.0
    modified_result = factor.run(modified).data
    unaffected = original["code"] == "000001"
    np.testing.assert_allclose(
        baseline.loc[unaffected].to_numpy(),
        modified_result.loc[unaffected].to_numpy(),
        equal_nan=True,
    )

    # 5. Future data contamination test
    baseline = factor.run(original).data
    future_modified = original.copy()
    future_date = future_modified["date"].max()
    future_mask = future_modified["date"] == future_date
    future_modified.loc[future_mask, "close"] *= 100.0
    future_result = factor.run(future_modified).data
    historical_mask = original["date"] < future_date
    np.testing.assert_allclose(
        baseline.loc[historical_mask].to_numpy(),
        future_result.loc[historical_mask].to_numpy(),
        equal_nan=True,
    )

    # 6. 股票独立排序
    shuffled = (
        panel.sample(frac=1.0, random_state=123).reset_index(drop=True)
    )
    shuffled_result = factor.run(shuffled).data
    expected = (
        pd.DataFrame(
            {
                "code": panel["code"],
                "date": panel["date"],
                "value": baseline,
            }
        )
        .sort_values(["code", "date"])["value"]
        .to_numpy()
    )
    actual = (
        pd.DataFrame(
            {
                "code": shuffled["code"],
                "date": shuffled["date"],
                "value": shuffled_result,
            }
        )
        .sort_values(["code", "date"])["value"]
        .to_numpy()
    )
    np.testing.assert_allclose(expected, actual, equal_nan=True)

    # 7. 输出范围测试
    rsi = RSIFactorV392(14).run(panel)
    valid_rsi = rsi.data.dropna()
    assert (
        (valid_rsi >= 0).all() and (valid_rsi <= 100).all()
    )

    # 8. Close Location
    clv = CloseLocationFactorV392().run(panel)
    valid_clv = clv.data.dropna()
    assert (
        (valid_clv >= 0).all() and (valid_clv <= 1).all()
    )

    print("Technical factor V3.9.2 self-test passed.")


if __name__ == "__main__":
    run_self_test_v392()
