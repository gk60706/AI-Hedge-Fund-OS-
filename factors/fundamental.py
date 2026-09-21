"""V3.9.2 Fundamental Factor Library (step13 factors/fundamental.py).

基本面因子库。

核心原则：
1. 基本面数据必须尊重 available_date。
2. 不允许把报告期(report_period)直接当成可用日期。
3. strict PIT 模式下，没有 available_date / announcement_date
   的基本面数据不能参与历史 Alpha 研究。
4. 因子计算只使用 as-of-date 当时已经公开的数据。
5. Fundamental Factor 与 Technical Factor 分离。
6. 不负责未来收益、回测和交易执行。

支持因子：

Value:
- Earnings Yield
- Book-to-Market
- Sales Yield
- PE Inverse
- PB Inverse
- PS Inverse

Quality:
- ROE
- ROIC
- Profit Margin
- Asset Turnover
- Financial Leverage

Growth:
- Revenue Growth
- Profit Growth
- Earnings Growth
- ROE Growth

Size:
- Market Cap
- Log Market Cap

Composite:
- Value Composite
- Quality Composite
- Growth Composite

注意：
---------------
如果数据没有真实的 available_date，
本模块不会自动把 report_period 当成 available_date。

这是为了防止：
    2024 年年报
被错误地用于：
    2024-01-01

这种典型 look-ahead bias。
"""

from abc import ABC
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

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
class FundamentalFactorErrorV392(Exception):
    """基本面因子异常。"""


class FundamentalFactorInputErrorV392(FundamentalFactorErrorV392):
    """基本面因子输入错误。"""


class FundamentalPITErrorV392(FundamentalFactorErrorV392):
    """基本面 PIT 数据错误。"""


# ============================================================
# Utilities
# ============================================================
def _numeric_v392(series: pd.Series) -> pd.Series:
    """转换为数值并清理无穷值。"""
    result = pd.to_numeric(
        series, errors="coerce",
    )
    return result.replace(
        [np.inf, -np.inf], np.nan,
    ).astype(float)


def _safe_divide_v392(
    numerator: pd.Series,
    denominator: pd.Series,
) -> pd.Series:
    """安全除法。"""
    numerator = _numeric_v392(numerator)
    denominator = _numeric_v392(denominator)
    denominator = denominator.replace(
        [np.inf, -np.inf, 0], np.nan,
    )
    result = numerator / denominator
    return result.replace(
        [np.inf, -np.inf], np.nan,
    )


def _check_columns_v392(
    data: pd.DataFrame,
    columns: Sequence[str],
) -> None:
    """检查输入字段。"""
    missing = [
        col for col in columns if col not in data.columns
    ]
    if missing:
        raise FundamentalFactorInputErrorV392(
            f"Missing required columns: {missing}"
        )


def _prepare_v392(data: pd.DataFrame) -> pd.DataFrame:
    """基本面统一数据准备。

    这里不排序、不修改原 index。
    基本面数据通常已经是：
        stock/date/report_period/available_date

    因子本身只负责在合法 PIT 数据上计算。
    """
    if not isinstance(data, pd.DataFrame):
        raise FundamentalFactorInputErrorV392(
            "data must be pandas.DataFrame"
        )
    result = data.copy()
    if "code" in result.columns:
        result["code"] = result["code"].astype(str).str.strip()
    if "date" in result.columns:
        result["date"] = pd.to_datetime(
            result["date"], errors="coerce",
        )
    if "available_date" in result.columns:
        result["available_date"] = pd.to_datetime(
            result["available_date"], errors="coerce",
        )
    if "announcement_date" in result.columns:
        result["announcement_date"] = pd.to_datetime(
            result["announcement_date"], errors="coerce",
        )
    return result


def _restore_series_v392(
    original_index: pd.Index,
    values: pd.Series,
) -> pd.Series:
    """恢复原始 index。"""
    result = pd.Series(
        values.to_numpy(),
        index=original_index,
        dtype=float,
    )
    return result.replace(
        [np.inf, -np.inf], np.nan,
    )


# ============================================================
# PIT Validation
# ============================================================
@dataclass
class FundamentalPITConfigV392:
    """基本面 PIT 配置。"""

    available_date_column: str = "available_date"
    announcement_date_column: str = "announcement_date"
    allow_announcement_fallback: bool = True
    strict: bool = True
    keep_unknown: bool = False


class FundamentalPITMixinV392:
    """基本面因子 PIT 检查。

    注意：
        report_period != available_date

    只有真实公开日期才能作为历史可用日期。
    """

    pit_config: FundamentalPITConfigV392

    def _validate_pit_v392(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392],
    ) -> None:
        if not self.pit_config.strict:
            return
        if context is None:
            raise FundamentalPITErrorV392(
                "Strict PIT requires FactorContext "
                "with as_of_date."
            )
        as_of_date = pd.Timestamp(context.as_of_date).normalize()
        available_col = (
            self.pit_config.available_date_column
        )
        announcement_col = (
            self.pit_config.announcement_date_column
        )
        if available_col not in data.columns:
            if (
                self.pit_config.allow_announcement_fallback
                and announcement_col in data.columns
            ):
                available = pd.to_datetime(
                    data[announcement_col], errors="coerce",
                )
            else:
                raise FundamentalPITErrorV392(
                    "Strict PIT mode requires "
                    f"'{available_col}' or a valid "
                    f"'{announcement_col}'."
                )
        else:
            available = pd.to_datetime(
                data[available_col], errors="coerce",
            )
        if (
            self.pit_config.allow_announcement_fallback
            and announcement_col in data.columns
        ):
            fallback = pd.to_datetime(
                data[announcement_col], errors="coerce",
            )
            available = available.fillna(fallback)
        unknown = available.isna()
        if (
            unknown.any()
            and not self.pit_config.keep_unknown
        ):
            raise FundamentalPITErrorV392(
                "Fundamental data contains rows "
                "without known availability date."
            )
        future = (
            available.notna() & (available > as_of_date)
        )
        if future.any():
            raise FundamentalPITErrorV392(
                "Future fundamental data detected. "
                f"{int(future.sum())} rows have "
                "availability date after "
                f"{as_of_date.date()}."
            )


# ============================================================
# Base Fundamental Factor
# ============================================================
class FundamentalFactorV392(
    FundamentalPITMixinV392,
    BaseFactorV392,
    ABC,
):
    """基本面因子基类。"""

    def __init__(
        self,
        config: FactorConfigV392,
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        super().__init__(config)
        self.pit_config = (
            pit_config or FundamentalPITConfigV392()
        )

    def _prepare_and_validate_v392(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392],
        numeric_columns: Sequence[str],
    ) -> pd.DataFrame:
        self.validate_input(data)
        work = _prepare_v392(data)
        self._validate_pit_v392(work, context)
        for col in numeric_columns:
            if col in work.columns:
                work[col] = _numeric_v392(work[col])
        return work


# ============================================================
# Earnings Yield
# ============================================================
class EarningsYieldFactorV392(FundamentalFactorV392):
    """盈利收益率。

    earnings_yield = 1 / PE

    PE 越低：
        earnings yield 越高。
    """

    def __init__(
        self,
        name: str = "earnings_yield",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Inverse PE / earnings yield."
            ),
            required_columns=[
                "code", "date", "pe",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "value",
                "formula": "1 / PE",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            ["pe"],
        )
        pe = work["pe"]
        result = _safe_divide_v392(
            pd.Series(
                1.0,
                index=work.index,
            ),
            pe,
        )
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# Book To Market
# ============================================================
class BookToMarketFactorV392(FundamentalFactorV392):
    """Book-to-Market。

    如果 PB = Price / Book：
        B/M = 1 / PB
    """

    def __init__(
        self,
        name: str = "book_to_market",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Inverse PB / book-to-market."
            ),
            required_columns=[
                "code", "date", "pb",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "value",
                "formula": "1 / PB",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            ["pb"],
        )
        result = _safe_divide_v392(
            pd.Series(
                1.0,
                index=work.index,
            ),
            work["pb"],
        )
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# Sales Yield
# ============================================================
class SalesYieldFactorV392(FundamentalFactorV392):
    """Sales Yield。

    如果 PS = Market Cap / Sales：
        Sales Yield = 1 / PS
    """

    def __init__(
        self,
        name: str = "sales_yield",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Inverse PS / sales yield."
            ),
            required_columns=[
                "code", "date", "ps",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "value",
                "formula": "1 / PS",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            ["ps"],
        )
        result = _safe_divide_v392(
            pd.Series(
                1.0,
                index=work.index,
            ),
            work["ps"],
        )
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# ROE
# ============================================================
class ROEFactorV392(FundamentalFactorV392):
    """Return on Equity。

    直接使用输入的 ROE。
    """

    def __init__(
        self,
        name: str = "roe",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description="Return on equity.",
            required_columns=[
                "code", "date", "roe",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "quality",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            ["roe"],
        )
        return _restore_series_v392(
            original_index,
            work["roe"],
        )


# ============================================================
# ROIC
# ============================================================
class ROICFactorV392(FundamentalFactorV392):
    """Return on Invested Capital。

    直接使用 ROIC 字段。
    """

    def __init__(
        self,
        name: str = "roic",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Return on invested capital."
            ),
            required_columns=[
                "code", "date", "roic",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "quality",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            ["roic"],
        )
        return _restore_series_v392(
            original_index,
            work["roic"],
        )


# ============================================================
# Profit Margin
# ============================================================
class ProfitMarginFactorV392(FundamentalFactorV392):
    """净利润率。

    如果已有：
        profit_margin

    直接使用。

    否则可以根据：
        net_profit / revenue
    计算。
    """

    def __init__(
        self,
        name: str = "profit_margin",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Net profit margin."
            ),
            required_columns=[
                "code", "date", "revenue", "net_profit",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "quality",
                "formula": (
                    "net_profit / revenue"
                ),
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "revenue",
                "net_profit",
            ],
        )
        result = _safe_divide_v392(
            work["net_profit"],
            work["revenue"],
        )
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# Asset Turnover
# ============================================================
class AssetTurnoverFactorV392(FundamentalFactorV392):
    """总资产周转率。

        Asset Turnover =
            Revenue / Total Assets
    """

    def __init__(
        self,
        name: str = "asset_turnover",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Revenue divided by total assets."
            ),
            required_columns=[
                "code", "date", "revenue", "total_assets",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "quality",
                "formula": (
                    "revenue / total_assets"
                ),
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "revenue",
                "total_assets",
            ],
        )
        result = _safe_divide_v392(
            work["revenue"],
            work["total_assets"],
        )
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# Financial Leverage
# ============================================================
class FinancialLeverageFactorV392(FundamentalFactorV392):
    """财务杠杆。

        Financial Leverage =
            Total Assets / Equity
    """

    def __init__(
        self,
        name: str = "financial_leverage",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Financial leverage measured as "
                "total assets divided by equity."
            ),
            required_columns=[
                "code", "date", "total_assets", "equity",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.NEGATIVE,
            higher_is_better=False,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "quality",
                "formula": (
                    "total_assets / equity"
                ),
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "total_assets",
                "equity",
            ],
        )
        result = _safe_divide_v392(
            work["total_assets"],
            work["equity"],
        )
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# Revenue Growth
# ============================================================
class RevenueGrowthFactorV392(FundamentalFactorV392):
    """营收增长率。

    支持两种模式：

    1. 数据已经存在 revenue_growth
    2. 根据 revenue 和 previous_revenue 计算

    默认要求：
        revenue_growth

    防止在没有明确报告期对齐逻辑时，
    自行跨期计算产生错误。
    """

    def __init__(
        self,
        name: str = "revenue_growth",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Revenue growth rate."
            ),
            required_columns=[
                "code", "date", "revenue_growth",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "growth",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "revenue_growth",
            ],
        )
        return _restore_series_v392(
            original_index,
            work["revenue_growth"],
        )


# ============================================================
# Profit Growth
# ============================================================
class ProfitGrowthFactorV392(FundamentalFactorV392):
    """净利润增长率。"""

    def __init__(
        self,
        name: str = "profit_growth",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Net profit growth rate."
            ),
            required_columns=[
                "code", "date", "profit_growth",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "growth",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "profit_growth",
            ],
        )
        return _restore_series_v392(
            original_index,
            work["profit_growth"],
        )


# ============================================================
# ROE Growth
# ============================================================
class ROEGrowthFactorV392(FundamentalFactorV392):
    """ROE 增长。

    需要：
        roe_growth

    不直接对当前 ROE 做 shift，
    避免混淆不同报告期。
    """

    def __init__(
        self,
        name: str = "roe_growth",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "ROE growth/change."
            ),
            required_columns=[
                "code", "date", "roe_growth",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "growth",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "roe_growth",
            ],
        )
        return _restore_series_v392(
            original_index,
            work["roe_growth"],
        )


# ============================================================
# Market Cap
# ============================================================
class MarketCapFactorV392(FundamentalFactorV392):
    """市值因子。

    如果输入：
        market_cap

    直接使用。

    该因子本身数值越大代表公司规模越大。
    """

    def __init__(
        self,
        name: str = "market_cap",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Market capitalization."
            ),
            required_columns=[
                "code", "date", "market_cap",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.NEUTRAL,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "size",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "market_cap",
            ],
        )
        return _restore_series_v392(
            original_index,
            work["market_cap"],
        )


# ============================================================
# Log Market Cap
# ============================================================
class LogMarketCapFactorV392(FundamentalFactorV392):
    """对数市值。

        log_market_cap = log(market_cap)

    常用于：
        Size Neutralization
    """

    def __init__(
        self,
        name: str = "log_market_cap",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Natural logarithm of market capitalization."
            ),
            required_columns=[
                "code", "date", "market_cap",
            ],
            output_column=name,
            scope=FactorScopeV392.FUNDAMENTAL,
            direction=FactorDirectionV392.NEUTRAL,
            higher_is_better=False,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "size",
                "formula": "log(market_cap)",
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "market_cap",
            ],
        )
        market_cap = (
            work["market_cap"].where(
                work["market_cap"] > 0
            )
        )
        result = np.log(market_cap)
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# Composite Factors
# ============================================================
def _cross_section_rank_v392(
    series: pd.Series,
    dates: pd.Series,
) -> pd.Series:
    """按日期横截面 percentile rank。"""
    return (
        series.groupby(
            dates, sort=False,
        ).rank(
            pct=True,
            method="average",
        )
    )


class ValueCompositeFactorV392(FundamentalFactorV392):
    """Value Composite。

    默认组合：

        rank(Earnings Yield)
        +
        rank(Book-to-Market)
        +
        rank(Sales Yield)

    / 3

    所有输入必须来自当前 PIT 数据。
    """

    def __init__(
        self,
        name: str = "value_composite",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Composite value factor using "
                "earnings yield, book-to-market "
                "and sales yield."
            ),
            required_columns=[
                "code", "date", "pe", "pb", "ps",
            ],
            output_column=name,
            scope=FactorScopeV392.COMPOSITE,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "value",
                "components": [
                    "earnings_yield",
                    "book_to_market",
                    "sales_yield",
                ],
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "pe",
                "pb",
                "ps",
            ],
        )
        earnings_yield = _safe_divide_v392(
            pd.Series(
                1.0,
                index=work.index,
            ),
            work["pe"],
        )
        book_to_market = _safe_divide_v392(
            pd.Series(
                1.0,
                index=work.index,
            ),
            work["pb"],
        )
        sales_yield = _safe_divide_v392(
            pd.Series(
                1.0,
                index=work.index,
            ),
            work["ps"],
        )
        r1 = _cross_section_rank_v392(
            earnings_yield,
            work["date"],
        )
        r2 = _cross_section_rank_v392(
            book_to_market,
            work["date"],
        )
        r3 = _cross_section_rank_v392(
            sales_yield,
            work["date"],
        )
        result = (
            r1 + r2 + r3
        ) / 3.0
        return _restore_series_v392(
            original_index,
            result,
        )


class QualityCompositeFactorV392(FundamentalFactorV392):
    """Quality Composite。

        rank(ROE)
        +
        rank(ROIC)
        +
        rank(Profit Margin)
        -
        rank(Financial Leverage)

    / 4
    """

    def __init__(
        self,
        name: str = "quality_composite",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Composite quality factor."
            ),
            required_columns=[
                "code", "date",
                "roe", "roic",
                "revenue", "net_profit",
                "total_assets", "equity",
            ],
            output_column=name,
            scope=FactorScopeV392.COMPOSITE,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "quality",
                "components": [
                    "roe",
                    "roic",
                    "profit_margin",
                    "financial_leverage",
                ],
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "roe",
                "roic",
                "revenue",
                "net_profit",
                "total_assets",
                "equity",
            ],
        )
        profit_margin = _safe_divide_v392(
            work["net_profit"],
            work["revenue"],
        )
        leverage = _safe_divide_v392(
            work["total_assets"],
            work["equity"],
        )
        roe_rank = _cross_section_rank_v392(
            work["roe"],
            work["date"],
        )
        roic_rank = _cross_section_rank_v392(
            work["roic"],
            work["date"],
        )
        margin_rank = _cross_section_rank_v392(
            profit_margin,
            work["date"],
        )
        leverage_rank = _cross_section_rank_v392(
            leverage,
            work["date"],
        )
        result = (
            roe_rank
            + roic_rank
            + margin_rank
            + (1.0 - leverage_rank)
        ) / 4.0
        return _restore_series_v392(
            original_index,
            result,
        )


class GrowthCompositeFactorV392(FundamentalFactorV392):
    """Growth Composite。

        rank(revenue_growth)
        +
        rank(profit_growth)
        +
        rank(roe_growth)

    / 3
    """

    def __init__(
        self,
        name: str = "growth_composite",
        pit_config: Optional[FundamentalPITConfigV392] = None,
    ):
        config = FactorConfigV392(
            name=name,
            version="3.9.2",
            description=(
                "Composite growth factor."
            ),
            required_columns=[
                "code", "date",
                "revenue_growth",
                "profit_growth",
                "roe_growth",
            ],
            output_column=name,
            scope=FactorScopeV392.COMPOSITE,
            direction=FactorDirectionV392.POSITIVE,
            higher_is_better=True,
            min_obs=1,
            require_available_date=True,
            metadata={
                "family": "growth",
                "components": [
                    "revenue_growth",
                    "profit_growth",
                    "roe_growth",
                ],
            },
        )
        super().__init__(config, pit_config)

    def compute(
        self,
        data: pd.DataFrame,
        context: Optional[FactorContextV392] = None,
    ) -> pd.Series:
        original_index = data.index
        work = self._prepare_and_validate_v392(
            data,
            context,
            [
                "revenue_growth",
                "profit_growth",
                "roe_growth",
            ],
        )
        r1 = _cross_section_rank_v392(
            work["revenue_growth"],
            work["date"],
        )
        r2 = _cross_section_rank_v392(
            work["profit_growth"],
            work["date"],
        )
        r3 = _cross_section_rank_v392(
            work["roe_growth"],
            work["date"],
        )
        result = (
            r1 + r2 + r3
        ) / 3.0
        return _restore_series_v392(
            original_index,
            result,
        )


# ============================================================
# Registry
# ============================================================
def build_default_fundamental_factors_v392(
    strict_pit: bool = True,
) -> List[FundamentalFactorV392]:
    """构建默认基本面因子库。"""
    pit_config = FundamentalPITConfigV392(
        strict=strict_pit,
        allow_announcement_fallback=True,
        keep_unknown=False,
    )
    return [
        # Value
        EarningsYieldFactorV392(pit_config=pit_config),
        BookToMarketFactorV392(pit_config=pit_config),
        SalesYieldFactorV392(pit_config=pit_config),
        # Quality
        ROEFactorV392(pit_config=pit_config),
        ROICFactorV392(pit_config=pit_config),
        ProfitMarginFactorV392(pit_config=pit_config),
        AssetTurnoverFactorV392(pit_config=pit_config),
        FinancialLeverageFactorV392(pit_config=pit_config),
        # Growth
        RevenueGrowthFactorV392(pit_config=pit_config),
        ProfitGrowthFactorV392(pit_config=pit_config),
        ROEGrowthFactorV392(pit_config=pit_config),
        # Size
        MarketCapFactorV392(pit_config=pit_config),
        LogMarketCapFactorV392(pit_config=pit_config),
        # Composite
        ValueCompositeFactorV392(pit_config=pit_config),
        QualityCompositeFactorV392(pit_config=pit_config),
        GrowthCompositeFactorV392(pit_config=pit_config),
    ]


def fundamental_factor_registry_v392(
    strict_pit: bool = True,
) -> Dict[str, FundamentalFactorV392]:
    """基本面因子 Registry。"""
    factors = (
        build_default_fundamental_factors_v392(
            strict_pit=strict_pit
        )
    )
    return {
        factor.name: factor
        for factor in factors
    }


# ============================================================
# Batch computation
# ============================================================
def compute_fundamental_factors_v392(
    data: pd.DataFrame,
    factors: Optional[Sequence[FundamentalFactorV392]] = None,
    context: Optional[FactorContextV392] = None,
) -> pd.DataFrame:
    """批量计算基本面因子。

    注意：
    strict PIT 模式必须提供 context。
    """
    if factors is None:
        factors = (
            build_default_fundamental_factors_v392(
                strict_pit=True
            )
        )
    result = data.copy()
    for factor in factors:
        factor_result = factor.run(
            result,
            context=context,
        )
        result[factor.output_column] = (
            factor_result.data
        )
    return result


# ============================================================
# Metadata
# ============================================================
def fundamental_factor_metadata_v392(
    strict_pit: bool = True,
) -> List[Dict]:
    """返回基本面因子元数据。"""
    factors = (
        build_default_fundamental_factors_v392(
            strict_pit=strict_pit
        )
    )
    return [
        factor.get_metadata()
        for factor in factors
    ]


# ============================================================
# Self Test
# ============================================================
def _test_context_v392() -> FactorContextV392:
    """创建测试 Context。"""
    return FactorContextV392(
        as_of_date=pd.Timestamp("2025-06-30"),
        universe=[
            "600000",
            "000001",
            "300001",
        ],
        data_version="test",
        experiment_id="fundamental-self-test",
    )


def _create_fundamental_test_data_v392() -> pd.DataFrame:
    """创建 PIT 测试数据。"""
    return pd.DataFrame(
        {
            "code": [
                "600000",
                "000001",
                "300001",
            ],
            "date": pd.to_datetime(
                [
                    "2025-06-30",
                    "2025-06-30",
                    "2025-06-30",
                ]
            ),
            "available_date": pd.to_datetime(
                [
                    "2025-04-30",
                    "2025-05-10",
                    "2025-06-01",
                ]
            ),
            "pe": [
                10.0,
                20.0,
                30.0,
            ],
            "pb": [
                1.0,
                2.0,
                3.0,
            ],
            "ps": [
                1.0,
                2.0,
                3.0,
            ],
            "roe": [
                0.20,
                0.15,
                0.10,
            ],
            "roic": [
                0.18,
                0.14,
                0.08,
            ],
            "revenue": [
                1000.0,
                1000.0,
                1000.0,
            ],
            "net_profit": [
                200.0,
                150.0,
                100.0,
            ],
            "total_assets": [
                2000.0,
                2500.0,
                3000.0,
            ],
            "equity": [
                1000.0,
                1000.0,
                1000.0,
            ],
            "revenue_growth": [
                0.20,
                0.10,
                0.05,
            ],
            "profit_growth": [
                0.30,
                0.15,
                0.05,
            ],
            "roe_growth": [
                0.10,
                0.05,
                -0.02,
            ],
            "market_cap": [
                100e8,
                50e8,
                20e8,
            ],
        }
    )


def run_self_test_v392() -> None:
    """基本面因子自测。"""
    data = (
        _create_fundamental_test_data_v392()
    )
    context = _test_context_v392()
    # --------------------------------------------------------
    # 1. PIT 正常
    # --------------------------------------------------------
    factor = EarningsYieldFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert (
        len(result.data) == len(data)
    )
    assert (
        result.data.index.equals(
            data.index
        )
    )
    # PE 10 -> 0.1
    assert np.isclose(
        result.data.iloc[0],
        0.1,
    )
    # --------------------------------------------------------
    # 2. Book-to-Market
    # --------------------------------------------------------
    factor = BookToMarketFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert np.isclose(
        result.data.iloc[0],
        1.0,
    )
    # --------------------------------------------------------
    # 3. ROE
    # --------------------------------------------------------
    factor = ROEFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert np.isclose(
        result.data.iloc[0],
        0.20,
    )
    # --------------------------------------------------------
    # 4. Profit Margin
    # --------------------------------------------------------
    factor = ProfitMarginFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert np.isclose(
        result.data.iloc[0],
        0.20,
    )
    # --------------------------------------------------------
    # 5. Market Cap
    # --------------------------------------------------------
    factor = MarketCapFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert np.isclose(
        result.data.iloc[0],
        100e8,
    )
    # --------------------------------------------------------
    # 6. Log Market Cap
    # --------------------------------------------------------
    factor = LogMarketCapFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert (
        np.isfinite(
            result.data.dropna()
        )
    ).all()
    # --------------------------------------------------------
    # 7. Value Composite
    # --------------------------------------------------------
    factor = ValueCompositeFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert (
        result.data.notna().sum() == 3
    )
    assert (
        (result.data >= 0).all()
        and (result.data <= 1).all()
    )
    # --------------------------------------------------------
    # 8. Quality Composite
    # --------------------------------------------------------
    factor = QualityCompositeFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert (
        result.data.notna().sum() == 3
    )
    # --------------------------------------------------------
    # 9. Growth Composite
    # --------------------------------------------------------
    factor = GrowthCompositeFactorV392()
    result = factor.run(
        data,
        context=context,
    )
    assert (
        result.data.notna().sum() == 3
    )
    # --------------------------------------------------------
    # 10. Future PIT detection
    # --------------------------------------------------------
    bad_data = data.copy()
    bad_data.loc[
        0,
        "available_date",
    ] = pd.Timestamp("2025-07-01")
    failed = False
    try:
        EarningsYieldFactorV392().run(
            bad_data,
            context=context,
        )
    except FundamentalPITErrorV392:
        failed = True
    assert failed
    # --------------------------------------------------------
    # 11. Unknown PIT detection
    # --------------------------------------------------------
    unknown_data = data.copy()
    unknown_data.loc[
        0,
        "available_date",
    ] = pd.NaT
    failed = False
    try:
        EarningsYieldFactorV392().run(
            unknown_data,
            context=context,
        )
    except FundamentalPITErrorV392:
        failed = True
    assert failed
    # --------------------------------------------------------
    # 12. Announcement date fallback
    # --------------------------------------------------------
    fallback_data = data.drop(
        columns=[
            "available_date"
        ]
    ).copy()
    fallback_data[
        "announcement_date"
    ] = pd.to_datetime(
        [
            "2025-04-30",
            "2025-05-10",
            "2025-06-01",
        ]
    )
    result = EarningsYieldFactorV392().run(
        fallback_data,
        context=context,
    )
    assert np.isclose(
        result.data.iloc[0],
        0.1,
    )
    print(
        "Fundamental factor V3.9.2 self-test passed."
    )


if __name__ == "__main__":
    run_self_test_v392()
