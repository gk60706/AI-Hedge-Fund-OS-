from __future__ import annotations

from factors.value import (
    PEFactor,
    PBFactor,
    PSFactor,
)
from factors.momentum import (
    MomentumFactor,
    Momentum60Factor,
    Momentum120Factor,
)
from factors.quality import (
    ROEFactor,
    ROICFactor,
    RevenueGrowthFactor,
    ProfitGrowthFactor,
)
from factors.volatility import (
    VolatilityFactor,
)
from factors.liquidity import (
    TurnoverFactor,
    Amount20Factor,
)


class FactorFactory:
    @staticmethod
    def default_factors():
        return [
            PEFactor(),
            PBFactor(),
            PSFactor(),
            MomentumFactor(20),
            Momentum60Factor(),
            Momentum120Factor(),
            ROEFactor(),
            ROICFactor(),
            RevenueGrowthFactor(),
            ProfitGrowthFactor(),
            VolatilityFactor(20),
            TurnoverFactor(),
            Amount20Factor(),
        ]


# ============================================================================
# V3.9.1 unified research engine - module-level default factors
# ============================================================================


def default_factors():
    from factors.value import ValueFactor
    from factors.quality import QualityFactor
    from factors.liquidity import LiquidityFactor

    return [ValueFactor(), QualityFactor(), LiquidityFactor()]


# ============================================================================
# V3.9.2 step14 - Factor Factory (PIT -> Technical/Fundamental -> Transform
# -> Neutralization -> Factor Matrix)
# ============================================================================
from dataclasses import dataclass, field as _field_v392
from datetime import datetime as _dt_v392, timezone as _tz_v392
from typing import Dict as _DictV392, List as _ListV392, Optional as _OptV392, Sequence as _SeqV392

import numpy as _np_v392
import pandas as _pd_v392

from .base import (
    BaseFactorV392,
    FactorContextV392,
)
from .technical import (
    TechnicalFactorV392,
    build_default_technical_factors_v392,
    MomentumFactorV392,
)
from .fundamental import (
    FundamentalFactorV392,
    build_default_fundamental_factors_v392,
)
from .transforms import (
    winsorize_by_date_v392,
    rank_by_date_v392,
    zscore_by_date_v392,
    robust_zscore_by_date_v392,
)
from .neutralization import neutralize_factor_v392


class FactorFactoryErrorV392(Exception):
    """Factor Factory 基础异常。"""


class FactorFactoryInputErrorV392(FactorFactoryErrorV392):
    """输入数据异常。"""


class FactorFactoryConfigurationErrorV392(FactorFactoryErrorV392):
    """Factory 配置异常。"""


@dataclass
class FactorProcessingConfigV392:
    """单个 Factor 的处理配置。"""

    transform: str = "zscore"
    winsorize: bool = True
    winsor_method: str = "quantile"
    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    neutralize: bool = False
    neutralization_columns: _ListV392[str] = _field_v392(default_factory=list)
    neutralization_min_obs: int = 10
    keep_original: bool = True


@dataclass
class FactorFactoryConfigV392:
    """Factor Factory 总配置。"""

    strict_pit: bool = True
    default_transform: str = "zscore"
    winsorize: bool = True
    winsor_lower: float = 0.01
    winsor_upper: float = 0.99
    winsor_method: str = "quantile"
    neutralize: bool = False
    neutralization_columns: _ListV392[str] = _field_v392(default_factory=list)
    neutralization_min_obs: int = 10
    include_technical: bool = True
    include_fundamental: bool = True
    selected_factors: _OptV392[_ListV392[str]] = None
    keep_raw_factors: bool = True
    keep_processed_factors: bool = True
    fail_on_factor_error: bool = True
    experiment_id: str = "factor_factory"
    metadata: _DictV392 = _field_v392(default_factory=dict)


@dataclass
class FactorMatrixV392:
    """Factor Factory 最终输出。"""

    data: _pd_v392.DataFrame
    raw_columns: _ListV392[str]
    processed_columns: _ListV392[str]
    neutralized_columns: _ListV392[str]
    metadata: _DictV392 = _field_v392(default_factory=dict)
    diagnostics: _DictV392 = _field_v392(default_factory=dict)

    def factor_columns(self) -> _ListV392[str]:
        columns: _ListV392[str] = []
        for col in self.processed_columns:
            if col not in columns:
                columns.append(col)
        for col in self.neutralized_columns:
            if col not in columns:
                columns.append(col)
        return columns

    def raw_matrix(self) -> _pd_v392.DataFrame:
        cols = [c for c in self.raw_columns if c in self.data.columns]
        return self.data[cols].copy()

    def processed_matrix(self) -> _pd_v392.DataFrame:
        cols = [c for c in self.processed_columns if c in self.data.columns]
        return self.data[cols].copy()

    def neutralized_matrix(self) -> _pd_v392.DataFrame:
        cols = [c for c in self.neutralized_columns if c in self.data.columns]
        return self.data[cols].copy()


class FactorFactoryV392:
    """V3.9.2 Factor Factory。"""

    def __init__(
        self,
        config: _OptV392[FactorFactoryConfigV392] = None,
    ):
        self.config = config or FactorFactoryConfigV392()
        self._factors: _DictV392[str, BaseFactorV392] = {}
        self._factor_configs: _DictV392[str, FactorProcessingConfigV392] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        if self.config.include_technical:
            for factor in build_default_technical_factors_v392():
                self.register(factor)
        if self.config.include_fundamental:
            for factor in build_default_fundamental_factors_v392(
                strict_pit=self.config.strict_pit
            ):
                self.register(factor)

    def register(
        self,
        factor: BaseFactorV392,
        processing_config: _OptV392[FactorProcessingConfigV392] = None,
    ) -> None:
        if not isinstance(factor, BaseFactorV392):
            raise FactorFactoryConfigurationErrorV392(
                "factor must inherit BaseFactorV392."
            )
        name = factor.name
        self._factors[name] = factor
        if processing_config is None:
            processing_config = FactorProcessingConfigV392(
                transform=self.config.default_transform,
                winsorize=self.config.winsorize,
                winsor_method=self.config.winsor_method,
                winsor_lower=self.config.winsor_lower,
                winsor_upper=self.config.winsor_upper,
                neutralize=self.config.neutralize,
                neutralization_columns=list(self.config.neutralization_columns),
                neutralization_min_obs=self.config.neutralization_min_obs,
            )
        self._factor_configs[name] = processing_config

    def unregister(self, factor_name: str) -> None:
        self._factors.pop(factor_name, None)
        self._factor_configs.pop(factor_name, None)

    def get(self, factor_name: str) -> BaseFactorV392:
        if factor_name not in self._factors:
            raise KeyError(f"Factor not registered: {factor_name}")
        return self._factors[factor_name]

    def list_factors(self) -> _ListV392[str]:
        return list(self._factors.keys())

    def technical_factors(self) -> _ListV392[str]:
        return [
            name
            for name, factor in self._factors.items()
            if isinstance(factor, TechnicalFactorV392)
        ]

    def fundamental_factors(self) -> _ListV392[str]:
        return [
            name
            for name, factor in self._factors.items()
            if isinstance(factor, FundamentalFactorV392)
        ]

    def _selected_factor_names(
        self,
        factor_names: _OptV392[_SeqV392[str]] = None,
    ) -> _ListV392[str]:
        if factor_names is None:
            if self.config.selected_factors is not None:
                factor_names = self.config.selected_factors
            else:
                return self.list_factors()
        selected: _ListV392[str] = []
        for name in factor_names:
            if name not in self._factors:
                raise FactorFactoryConfigurationErrorV392(
                    f"Unknown factor: {name}"
                )
            selected.append(name)
        return selected

    def _transform(
        self,
        series: _pd_v392.Series,
        dates: _pd_v392.Series,
        config: FactorProcessingConfigV392,
    ) -> _pd_v392.Series:
        """对单个 Factor 进行 winsorize -> rank/zscore。"""
        work = _pd_v392.DataFrame(
            {"_value": _pd_v392.to_numeric(series, errors="coerce"), "_date": dates},
            index=series.index,
        )
        if config.winsorize:
            method = (config.winsor_method or "mad").lower()
            if method not in ("mad", "quantile"):
                method = "mad"
            work["_value"] = winsorize_by_date_v392(
                work,
                column="_value",
                date_column="_date",
                method=method,
                limit=3.0,
            )
        method = (config.transform or "zscore").lower().strip()
        if method == "raw":
            return work["_value"]
        if method == "rank":
            return rank_by_date_v392(
                work, column="_value", date_column="_date"
            )
        if method == "zscore":
            return zscore_by_date_v392(
                work, column="_value", date_column="_date"
            )
        if method == "robust_zscore":
            return robust_zscore_by_date_v392(
                work, column="_value", date_column="_date"
            )
        raise FactorFactoryConfigurationErrorV392(
            f"Unsupported transform: {config.transform}"
        )

    def _neutralize(
        self,
        data: _pd_v392.DataFrame,
        factor_column: str,
        config: FactorProcessingConfigV392,
    ) -> _pd_v392.Series:
        if not config.neutralize:
            return data[factor_column].copy()
        cols = config.neutralization_columns
        if not cols:
            raise FactorFactoryConfigurationErrorV392(
                f"Neutralization enabled for {factor_column} but no "
                "neutralization_columns configured."
            )
        industry_column: _OptV392[str] = None
        market_cap_column: _OptV392[str] = None
        for col in cols:
            lower = col.lower()
            if lower in {"industry", "industry_code", "industry_name"}:
                industry_column = col
            if lower in {"market_cap", "market_value", "total_market_value"}:
                market_cap_column = col
        if industry_column is None and market_cap_column is None:
            raise FactorFactoryConfigurationErrorV392(
                "Neutralization columns must contain industry or market_cap."
            )
        result, _diag = neutralize_factor_v392(
            data,
            factor_column,
            industry_column=industry_column or "industry",
            market_cap_column=market_cap_column or "market_cap",
            neutralize_industry=industry_column is not None,
            neutralize_size=market_cap_column is not None,
            min_obs=config.neutralization_min_obs,
        )
        return result

    @staticmethod
    def _build_context(
        data: _pd_v392.DataFrame,
        context: _OptV392[FactorContextV392],
    ) -> FactorContextV392:
        if context is not None:
            return context
        if "date" not in data.columns:
            raise FactorFactoryInputErrorV392("Data must contain date column.")
        dates = _pd_v392.to_datetime(data["date"], errors="coerce")
        if dates.isna().all():
            raise FactorFactoryInputErrorV392("Cannot infer as_of_date.")
        as_of_date = dates.max()
        universe: _ListV392[str] = []
        if "code" in data.columns:
            universe = (
                data["code"].astype(str).dropna().unique().tolist()
            )
        return FactorContextV392(
            as_of_date=as_of_date,
            universe=universe,
            data_version="unknown",
            experiment_id="factor_factory",
        )

    def build(
        self,
        data: _pd_v392.DataFrame,
        factor_names: _OptV392[_SeqV392[str]] = None,
        context: _OptV392[FactorContextV392] = None,
    ) -> FactorMatrixV392:
        if not isinstance(data, _pd_v392.DataFrame):
            raise FactorFactoryInputErrorV392("data must be pandas.DataFrame.")
        if data.empty:
            raise FactorFactoryInputErrorV392("data is empty.")
        if "date" not in data.columns:
            raise FactorFactoryInputErrorV392("data must contain date.")
        if "code" not in data.columns:
            raise FactorFactoryInputErrorV392("data must contain code.")
        result = data.copy()
        ctx = self._build_context(result, context)
        selected_names = self._selected_factor_names(factor_names)
        raw_columns: _ListV392[str] = []
        processed_columns: _ListV392[str] = []
        neutralized_columns: _ListV392[str] = []
        diagnostics: _DictV392 = {}

        for name in selected_names:
            factor = self._factors[name]
            processing_config = self._factor_configs[name]
            try:
                factor_result = factor.run(result, context=ctx)
                raw_name = f"{name}__raw"
                result[raw_name] = factor_result.data
                raw_columns.append(raw_name)
                diagnostics[name] = {
                    "factor": factor.get_metadata(),
                    "raw_summary": factor_result.summary(),
                }
                processed = self._transform(
                    factor_result.data,
                    _pd_v392.to_datetime(result["date"]),
                    processing_config,
                )
                processed_name = f"{name}__processed"
                result[processed_name] = processed
                processed_columns.append(processed_name)
                diagnostics[name]["processed_summary"] = {
                    "count": int(processed.notna().sum()),
                    "mean": float(processed.mean()) if processed.notna().any() else None,
                    "std": float(processed.std()) if processed.notna().any() else None,
                }
                if processing_config.neutralize:
                    neutralized = self._neutralize(
                        result, processed_name, processing_config
                    )
                    neutralized_name = f"{name}__neutralized"
                    result[neutralized_name] = neutralized
                    neutralized_columns.append(neutralized_name)
                    diagnostics[name]["neutralized_summary"] = {
                        "count": int(neutralized.notna().sum()),
                        "mean": (
                            float(neutralized.mean())
                            if neutralized.notna().any()
                            else None
                        ),
                        "std": (
                            float(neutralized.std())
                            if neutralized.notna().any()
                            else None
                        ),
                    }
            except Exception as exc:
                diagnostics[name] = {"status": "failed", "error": str(exc)}
                if self.config.fail_on_factor_error:
                    raise FactorFactoryErrorV392(
                        f"Factor '{name}' failed: {exc}"
                    ) from exc

        metadata = {
            "factory_version": "3.9.2",
            "experiment_id": self.config.experiment_id,
            "created_at": _dt_v392.now(_tz_v392.utc).isoformat(),
            "as_of_date": str(ctx.as_of_date),
            "universe_size": len(ctx.universe or []),
            "selected_factors": selected_names,
            "raw_factor_count": len(raw_columns),
            "processed_factor_count": len(processed_columns),
            "neutralized_factor_count": len(neutralized_columns),
            "config": {
                "strict_pit": self.config.strict_pit,
                "default_transform": self.config.default_transform,
                "winsorize": self.config.winsorize,
                "neutralize": self.config.neutralize,
            },
            "user_metadata": self.config.metadata,
        }
        return FactorMatrixV392(
            data=result,
            raw_columns=raw_columns,
            processed_columns=processed_columns,
            neutralized_columns=neutralized_columns,
            metadata=metadata,
            diagnostics=diagnostics,
        )

    def build_matrix(
        self,
        data: _pd_v392.DataFrame,
        factor_names: _OptV392[_SeqV392[str]] = None,
        context: _OptV392[FactorContextV392] = None,
        use_neutralized: bool = True,
    ) -> _pd_v392.DataFrame:
        matrix = self.build(
            data=data, factor_names=factor_names, context=context
        )
        columns = ["date", "code"]
        if use_neutralized and matrix.neutralized_columns:
            columns.extend(matrix.neutralized_columns)
        else:
            columns.extend(matrix.processed_columns)
        columns = [c for c in columns if c in matrix.data.columns]
        return matrix.data[columns].copy()

    def metadata(self) -> _DictV392:
        return {
            "version": "3.9.2",
            "factor_count": len(self._factors),
            "technical_factor_count": len(self.technical_factors()),
            "fundamental_factor_count": len(self.fundamental_factors()),
            "factors": {
                name: factor.get_metadata()
                for name, factor in self._factors.items()
            },
            "processing": {
                name: cfg.__dict__.copy()
                for name, cfg in self._factor_configs.items()
            },
        }


def build_factor_matrix_v392(
    data: _pd_v392.DataFrame,
    factor_names: _OptV392[_SeqV392[str]] = None,
    context: _OptV392[FactorContextV392] = None,
    config: _OptV392[FactorFactoryConfigV392] = None,
) -> FactorMatrixV392:
    """Convenience API."""
    factory = FactorFactoryV392(config=config)
    return factory.build(data=data, factor_names=factor_names, context=context)


def _create_technical_test_data_v392(n_days: int = 80) -> _pd_v392.DataFrame:
    dates = _pd_v392.bdate_range("2025-01-01", periods=n_days)
    rows: _ListV392[_DictV392] = []
    rng = _np_v392.random.default_rng(123)
    for code, base in [
        ("600000", 10.0),
        ("000001", 20.0),
        ("300001", 30.0),
    ]:
        returns = rng.normal(0.001, 0.02, n_days)
        close = base * _np_v392.cumprod(1 + returns)
        for i, date in enumerate(dates):
            c = close[i]
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "open": c,
                    "high": c * 1.01,
                    "low": c * 0.99,
                    "close": c,
                    "volume": 1e6 * (1 + rng.random()),
                    "amount": c * 1e6,
                    "turnover": 1 + rng.random() * 2,
                }
            )
    return _pd_v392.DataFrame(rows)


def _create_fundamental_test_data_v392() -> _pd_v392.DataFrame:
    return _pd_v392.DataFrame(
        {
            "code": ["600000", "000001", "300001"],
            "date": _pd_v392.to_datetime(
                ["2025-06-30", "2025-06-30", "2025-06-30"]
            ),
            "available_date": _pd_v392.to_datetime(
                ["2025-04-01", "2025-04-05", "2025-05-01"]
            ),
            "pe": [10.0, 20.0, 30.0],
            "pb": [1.0, 2.0, 3.0],
            "ps": [1.0, 2.0, 3.0],
            "roe": [0.20, 0.15, 0.10],
            "roic": [0.18, 0.14, 0.08],
            "revenue": [1000.0, 1000.0, 1000.0],
            "net_profit": [200.0, 150.0, 100.0],
            "total_assets": [2000.0, 2500.0, 3000.0],
            "equity": [1000.0, 1000.0, 1000.0],
            "revenue_growth": [0.20, 0.10, 0.05],
            "profit_growth": [0.30, 0.15, 0.05],
            "roe_growth": [0.10, 0.05, -0.02],
            "market_cap": [100e8, 50e8, 20e8],
        }
    )


def run_self_test_v392() -> None:
    # 1. Technical-only factory
    technical_data = _create_technical_test_data_v392()
    technical_config = FactorFactoryConfigV392(
        include_technical=True,
        include_fundamental=False,
        default_transform="zscore",
        winsorize=True,
        experiment_id="technical-test",
    )
    factory = FactorFactoryV392(technical_config)
    matrix = factory.build(
        technical_data,
        factor_names=["momentum_20", "volatility_20", "rsi_14"],
    )
    assert "momentum_20__raw" in matrix.data.columns
    assert "momentum_20__processed" in matrix.data.columns
    assert "rsi_14__processed" in matrix.data.columns
    assert len(matrix.raw_columns) == 3
    assert len(matrix.processed_columns) == 3

    # 2. Matrix API
    factor_matrix = factory.build_matrix(
        technical_data,
        factor_names=["momentum_20", "volatility_20"],
    )
    assert "date" in factor_matrix.columns
    assert "code" in factor_matrix.columns

    # 3. Fundamental-only factory
    fundamental_data = _create_fundamental_test_data_v392()
    fundamental_config = FactorFactoryConfigV392(
        include_technical=False,
        include_fundamental=True,
        strict_pit=True,
        default_transform="rank",
        experiment_id="fundamental-test",
    )
    fundamental_factory = FactorFactoryV392(fundamental_config)
    context = FactorContextV392(
        as_of_date=_pd_v392.Timestamp("2025-06-30"),
        universe=["600000", "000001", "300001"],
        data_version="test",
        experiment_id="fundamental-test",
    )
    fundamental_matrix = fundamental_factory.build(
        fundamental_data,
        factor_names=["earnings_yield", "roe", "roic"],
        context=context,
    )
    assert len(fundamental_matrix.processed_columns) == 3

    # 4. PIT future detection
    bad_data = fundamental_data.copy()
    bad_data.loc[0, "available_date"] = _pd_v392.Timestamp("2025-07-01")
    failed = False
    try:
        fundamental_factory.build(
            bad_data,
            factor_names=["earnings_yield"],
            context=context,
        )
    except FactorFactoryErrorV392:
        failed = True
    assert failed

    # 5. Custom factor registration
    custom_factory = FactorFactoryV392(
        FactorFactoryConfigV392(
            include_technical=False,
            include_fundamental=False,
        )
    )
    custom_factory.register(MomentumFactorV392(window=10))
    assert "momentum_10" in custom_factory.list_factors()

    # 6. Metadata
    md = factory.metadata()
    assert md["version"] == "3.9.2"
    assert md["factor_count"] >= 3

    print("Factor Factory V3.9.2 self-test passed.")


if __name__ == "__main__":
    run_self_test_v392()
