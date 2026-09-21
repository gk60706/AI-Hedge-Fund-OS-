from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Factor(ABC):
    name: str = "base"

    @abstractmethod
    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.Series:
        """
        返回与 data.index 对齐的因子值。
        """
        raise NotImplementedError


# ============================================================================
# V3.9.2 Factor Framework (step9 factors/base.py)
#
# 设计原则：
#   - 因子计算与数据获取解耦
#   - 因子计算与回测解耦
#   - 不在 BaseFactor 中偷偷填充未来数据
#   - 不允许静默忽略缺失字段
#   - 所有因子都必须明确 required_columns / lookback / direction
#
# 与旧版 Factor(ABC) 的关系：
#   - 旧版 Factor / calculate(data) 被 momentum/value/quality/volatility/
#     liquidity/test_v37_v38 依赖，完整保留
#   - 新版以 V392 后缀追加，子类只需要实现 compute()，
#     统一走 run() -> validate_input -> validate_pit -> validate_universe
#     -> compute -> normalize_output -> transform -> validate_output
#     -> diagnostics -> FactorResult
# ============================================================================

from abc import (
    ABC as _ABC_V392,
    abstractmethod as _abstractmethod_v392,
)
from dataclasses import (
    dataclass as _dataclass_v392,
    field as _field_v392,
)
from enum import Enum as _Enum_v392
from typing import (
    Any as _AnyV392,
    Callable as _CallableV392,
    Dict as _DictV392,
    Iterable as _IterableV392,
    List as _ListV392,
    Mapping as _MappingV392,
    Optional as _OptionalV392,
    Sequence as _SequenceV392,
    Union as _UnionV392,
)

import numpy as _np_v392


# ----------------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------------
class FactorErrorV392(Exception):
    """因子系统基础异常。"""


class FactorInputErrorV392(FactorErrorV392):
    """因子输入数据错误。"""


class FactorComputationErrorV392(FactorErrorV392):
    """因子计算错误。"""


# ----------------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------------
class FactorScopeV392(str, _Enum_v392):
    """因子作用范围。"""

    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"
    FUNDAMENTAL = "fundamental"
    TECHNICAL = "technical"
    COMPOSITE = "composite"


class FactorDirectionV392(str, _Enum_v392):
    """因子方向。"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


# ----------------------------------------------------------------------------
# Factor Config
# ----------------------------------------------------------------------------
@_dataclass_v392
class FactorConfigV392:
    """因子配置（每个 Factor 必须有明确元数据）。"""

    name: str
    version: str = "1.0"
    description: str = ""
    required_columns: _SequenceV392[str] = _field_v392(
        default_factory=list
    )
    output_column: _OptionalV392[str] = None
    lookback: int = 0
    horizon: int = 1
    scope: FactorScopeV392 = FactorScopeV392.CROSS_SECTIONAL
    direction: FactorDirectionV392 = FactorDirectionV392.NEUTRAL
    higher_is_better: _OptionalV392[bool] = None
    min_obs: int = 1
    allow_missing: bool = False
    winsorize: bool = False
    standardize: bool = False
    neutralize: bool = False
    neutralization_columns: _SequenceV392[str] = _field_v392(
        default_factory=list
    )
    require_available_date: bool = False
    require_code: bool = True
    require_date: bool = True
    allow_nan_output: bool = True
    metadata: _DictV392[str, _AnyV392] = _field_v392(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Factor name cannot be empty.")
        if self.lookback < 0:
            raise ValueError("lookback cannot be negative.")
        if self.horizon < 0:
            raise ValueError("horizon cannot be negative.")
        if self.min_obs < 1:
            raise ValueError("min_obs must be >= 1.")
        if self.output_column is None:
            self.output_column = self.name
        self.required_columns = list(self.required_columns)
        self.neutralization_columns = list(
            self.neutralization_columns
        )

    def to_dict(self) -> _DictV392[str, _AnyV392]:
        """转换成可持久化字典。"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "required_columns": list(self.required_columns),
            "output_column": self.output_column,
            "lookback": self.lookback,
            "horizon": self.horizon,
            "scope": self.scope.value,
            "direction": self.direction.value,
            "higher_is_better": self.higher_is_better,
            "min_obs": self.min_obs,
            "allow_missing": self.allow_missing,
            "winsorize": self.winsorize,
            "standardize": self.standardize,
            "neutralize": self.neutralize,
            "neutralization_columns": list(
                self.neutralization_columns
            ),
            "require_available_date": self.require_available_date,
            "require_code": self.require_code,
            "require_date": self.require_date,
            "allow_nan_output": self.allow_nan_output,
            "metadata": self.metadata,
        }


# ----------------------------------------------------------------------------
# Factor Context
# ----------------------------------------------------------------------------
@_dataclass_v392
class FactorContextV392:
    """因子执行上下文（as_of_date / universe / data_version / experiment_id）。"""

    as_of_date: _OptionalV392[pd.Timestamp] = None
    universe: _OptionalV392[_SequenceV392[str]] = None
    data_version: _OptionalV392[str] = None
    experiment_id: _OptionalV392[str] = None
    metadata: _DictV392[str, _AnyV392] = _field_v392(
        default_factory=dict
    )

    def normalized(self) -> "FactorContextV392":
        """返回标准化后的 Context。"""
        as_of_date = self.as_of_date
        if as_of_date is not None:
            as_of_date = pd.Timestamp(as_of_date).normalize()
        universe = None
        if self.universe is not None:
            universe = [
                str(code).strip()
                for code in self.universe
                if str(code).strip()
            ]
        return FactorContextV392(
            as_of_date=as_of_date,
            universe=universe,
            data_version=self.data_version,
            experiment_id=self.experiment_id,
            metadata=dict(self.metadata),
        )


# ----------------------------------------------------------------------------
# Factor Result
# ----------------------------------------------------------------------------
@_dataclass_v392
class FactorResultV392:
    """标准因子计算结果。"""

    data: pd.Series
    name: str
    version: str
    diagnostics: _DictV392[str, _AnyV392] = _field_v392(
        default_factory=dict
    )
    metadata: _DictV392[str, _AnyV392] = _field_v392(
        default_factory=dict
    )

    def to_frame(self) -> pd.DataFrame:
        """转换为 DataFrame。"""
        return self.data.rename(self.name).to_frame()

    def summary(self) -> _DictV392[str, _AnyV392]:
        """返回结果摘要。"""
        series = pd.to_numeric(self.data, errors="coerce")
        valid = series.dropna()
        result = {
            "name": self.name,
            "version": self.version,
            "rows": int(len(series)),
            "valid_rows": int(len(valid)),
            "missing_rows": int(series.isna().sum()),
        }
        if len(valid) > 0:
            result.update(
                {
                    "mean": float(valid.mean()),
                    "std": float(valid.std()),
                    "min": float(valid.min()),
                    "max": float(valid.max()),
                }
            )
        else:
            result.update(
                {
                    "mean": None,
                    "std": None,
                    "min": None,
                    "max": None,
                }
            )
        result.update(self.diagnostics)
        return result


# ----------------------------------------------------------------------------
# Base Factor
# ----------------------------------------------------------------------------
class BaseFactorV392(_ABC_V392):
    """所有因子的抽象基类。子类只需要实现 compute()。"""

    def __init__(self, config: FactorConfigV392) -> None:
        self.config = config

    # ---------------- Properties ----------------
    @property
    def name(self) -> str:
        return self.config.name

    @property
    def version(self) -> str:
        return self.config.version

    @property
    def output_column(self) -> str:
        return self.config.output_column or self.name

    @property
    def required_columns(self) -> _ListV392[str]:
        return list(self.config.required_columns)

    @property
    def lookback(self) -> int:
        return self.config.lookback

    @property
    def horizon(self) -> int:
        return self.config.horizon

    @property
    def scope(self) -> FactorScopeV392:
        return self.config.scope

    @property
    def direction(self) -> FactorDirectionV392:
        return self.config.direction

    # ---------------- Input Validation ----------------
    def validate_input(self, data: pd.DataFrame) -> None:
        """校验因子输入数据。"""
        if data is None:
            raise FactorInputErrorV392(
                f"Factor '{self.name}' received None input."
            )
        if not isinstance(data, pd.DataFrame):
            raise FactorInputErrorV392(
                f"Factor '{self.name}' requires pandas.DataFrame, "
                f"got {type(data).__name__}."
            )
        if data.empty:
            raise FactorInputErrorV392(
                f"Factor '{self.name}' received empty DataFrame."
            )

        required = set(self.required_columns)
        if self.config.require_code:
            required.add("code")
        if self.config.require_date:
            required.add("date")
        if self.config.require_available_date:
            required.add("available_date")

        missing = [
            column
            for column in required
            if column not in data.columns
        ]
        if missing and not self.config.allow_missing:
            raise FactorInputErrorV392(
                f"Factor '{self.name}' missing required columns: "
                f"{missing}"
            )

        if "date" in data.columns:
            parsed_dates = pd.to_datetime(
                data["date"], errors="coerce"
            )
            if parsed_dates.isna().all():
                raise FactorInputErrorV392(
                    f"Factor '{self.name}' has no valid dates."
                )
        if "code" in data.columns:
            valid_codes = (
                data["code"].astype(str).str.strip().ne("")
            )
            if not valid_codes.any():
                raise FactorInputErrorV392(
                    f"Factor '{self.name}' has no valid stock codes."
                )

    # ---------------- PIT Safety ----------------
    def validate_point_in_time(
        self,
        data: pd.DataFrame,
        context: _OptionalV392[FactorContextV392] = None,
    ) -> None:
        """检查 PIT 可用性（available_date <= as_of_date）。"""
        if not self.config.require_available_date:
            return
        if "available_date" not in data.columns:
            raise FactorInputErrorV392(
                f"Factor '{self.name}' requires PIT column "
                f"'available_date'."
            )
        available = pd.to_datetime(
            data["available_date"], errors="coerce"
        )
        if context is not None:
            ctx = context.normalized()
            if ctx.as_of_date is not None:
                future = (
                    available.notna()
                    & (available > ctx.as_of_date)
                )
                if future.any():
                    count = int(future.sum())
                    raise FactorInputErrorV392(
                        f"Factor '{self.name}' contains {count} "
                        f"rows with available_date after "
                        f"as_of_date={ctx.as_of_date.date()}."
                    )

    # ---------------- Universe Validation ----------------
    def validate_universe(
        self,
        data: pd.DataFrame,
        context: _OptionalV392[FactorContextV392] = None,
    ) -> None:
        """检查股票池（只记录，不删除范围外股票）。"""
        if context is None:
            return
        context = context.normalized()
        if context.universe is None:
            return
        if "code" not in data.columns:
            return

    # ---------------- Compute ----------------
    @_abstractmethod_v392
    def compute(
        self,
        data: pd.DataFrame,
        context: _OptionalV392[FactorContextV392] = None,
    ) -> _UnionV392[
        pd.Series,
        pd.DataFrame,
        _np_v392.ndarray,
        _SequenceV392[float],
    ]:
        """子类必须实现。推荐返回与 data.index 对齐的 pd.Series。"""
        raise NotImplementedError

    # ---------------- Output Normalization ----------------
    def _normalize_output(
        self,
        output: _UnionV392[
            pd.Series,
            pd.DataFrame,
            _np_v392.ndarray,
            _SequenceV392[float],
        ],
        data: pd.DataFrame,
    ) -> pd.Series:
        """将不同类型输出统一转换成 Series，并对齐 index。"""
        if isinstance(output, pd.DataFrame):
            if self.output_column in output.columns:
                output = output[self.output_column]
            elif len(output.columns) == 1:
                output = output.iloc[:, 0]
            else:
                raise FactorComputationErrorV392(
                    f"Factor '{self.name}' returned a DataFrame "
                    f"with multiple columns and no matching "
                    f"output column '{self.output_column}'."
                )
        elif isinstance(output, pd.Series):
            pass
        elif isinstance(output, _np_v392.ndarray):
            if output.ndim != 1:
                raise FactorComputationErrorV392(
                    f"Factor '{self.name}' returned ndarray with "
                    f"shape {output.shape}; expected 1D array."
                )
            output = pd.Series(output, index=data.index)
        else:
            try:
                output = pd.Series(output, index=data.index)
            except Exception as exc:
                raise FactorComputationErrorV392(
                    f"Factor '{self.name}' output cannot be "
                    f"converted to Series."
                ) from exc

        if len(output) != len(data):
            raise FactorComputationErrorV392(
                f"Factor '{self.name}' output length "
                f"{len(output)} != input length {len(data)}."
            )

        if not output.index.equals(data.index):
            try:
                output = output.reindex(data.index)
            except Exception as exc:
                raise FactorComputationErrorV392(
                    f"Factor '{self.name}' output index "
                    f"cannot be aligned with input index."
                ) from exc
        output.name = self.output_column
        return output

    # ---------------- Output Validation ----------------
    def validate_output(
        self,
        output: pd.Series,
        data: pd.DataFrame,
    ) -> None:
        """检查因子输出。"""
        if not isinstance(output, pd.Series):
            raise FactorComputationErrorV392(
                f"Factor '{self.name}' output must be Series."
            )
        if len(output) != len(data):
            raise FactorComputationErrorV392(
                f"Factor '{self.name}' output length mismatch."
            )
        if not self.config.allow_nan_output and output.isna().any():
            raise FactorComputationErrorV392(
                f"Factor '{self.name}' produced NaN output "
                f"while allow_nan_output=False."
            )
        numeric = pd.to_numeric(output, errors="coerce")
        if (
            numeric.notna().sum() < self.config.min_obs
        ):
            raise FactorComputationErrorV392(
                f"Factor '{self.name}' has only "
                f"{int(numeric.notna().sum())} valid observations; "
                f"minimum required={self.config.min_obs}."
            )
        if _np_v392.isinf(numeric.to_numpy()).any():
            raise FactorComputationErrorV392(
                f"Factor '{self.name}' produced infinite values."
            )

    # ---------------- Transform Hook ----------------
    def transform(
        self,
        output: pd.Series,
        data: pd.DataFrame,
        context: _OptionalV392[FactorContextV392] = None,
    ) -> pd.Series:
        """因子后处理 Hook（winsorize/rank/zscore/中性化由后续 transforms.py 承担）。"""
        return output

    # ---------------- Diagnostics ----------------
    def diagnostics(
        self,
        output: pd.Series,
        data: pd.DataFrame,
    ) -> _DictV392[str, _AnyV392]:
        """生成基础诊断信息。"""
        numeric = pd.to_numeric(output, errors="coerce")
        valid = numeric.dropna()
        result: _DictV392[str, _AnyV392] = {
            "input_rows": int(len(data)),
            "output_rows": int(len(output)),
            "valid_rows": int(valid.shape[0]),
            "missing_rows": int(numeric.isna().sum()),
            "missing_ratio": (
                float(numeric.isna().mean())
                if len(numeric) > 0
                else 1.0
            ),
            "lookback": int(self.lookback),
            "horizon": int(self.horizon),
            "scope": self.scope.value,
            "direction": self.direction.value,
        }
        if len(valid) > 0:
            result.update(
                {
                    "mean": float(valid.mean()),
                    "std": float(valid.std()),
                    "min": float(valid.min()),
                    "max": float(valid.max()),
                }
            )
        return result

    # ---------------- Run (主入口) ----------------
    def run(
        self,
        data: pd.DataFrame,
        context: _OptionalV392[FactorContextV392] = None,
    ) -> FactorResultV392:
        """执行完整因子流程：

        Input Validation → PIT Validation → Universe Validation → Compute
        → Normalize → Transform → Output Validation → Diagnostics → Result
        """
        if context is not None:
            context = context.normalized()
        # 1. 输入检查
        self.validate_input(data)
        # 2. PIT 检查
        self.validate_point_in_time(data, context)
        # 3. Universe 检查
        self.validate_universe(data, context)
        # 4. 因子计算
        try:
            raw_output = self.compute(data, context)
        except FactorErrorV392:
            raise
        except Exception as exc:
            raise FactorComputationErrorV392(
                f"Factor '{self.name}' computation failed: {exc}"
            ) from exc
        # 5. 输出标准化
        output = self._normalize_output(raw_output, data)
        # 6. 后处理
        output = self.transform(output, data, context)
        # 7. 再次标准化
        output = self._normalize_output(output, data)
        # 8. 输出检查
        self.validate_output(output, data)
        # 9. 诊断
        diagnostics = self.diagnostics(output, data)
        # 10. Context metadata
        metadata = self.get_metadata()
        if context is not None:
            metadata["context"] = {
                "as_of_date": (
                    context.as_of_date.isoformat()
                    if context.as_of_date is not None
                    else None
                ),
                "universe_size": (
                    len(context.universe)
                    if context.universe is not None
                    else None
                ),
                "data_version": context.data_version,
                "experiment_id": context.experiment_id,
            }
        return FactorResultV392(
            data=output,
            name=self.name,
            version=self.version,
            diagnostics=diagnostics,
            metadata=metadata,
        )

    # ---------------- Metadata ----------------
    def get_metadata(self) -> _DictV392[str, _AnyV392]:
        """返回完整因子元数据（Alpha Search / Experiment Registry 用）。"""
        return {
            **self.config.to_dict(),
            "class_name": self.__class__.__name__,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"version='{self.version}', "
            f"lookback={self.lookback}, "
            f"scope='{self.scope.value}')"
        )


# ----------------------------------------------------------------------------
# Callable Factor（把普通 Python 函数包装成 Factor）
# ----------------------------------------------------------------------------
class CallableFactorV392(BaseFactorV392):
    """将普通 Python 函数包装成 Factor，用于快速实验。"""

    def __init__(
        self,
        name: str,
        func: _CallableV392[
            [pd.DataFrame, _OptionalV392[FactorContextV392]],
            _UnionV392[
                pd.Series,
                pd.DataFrame,
                _np_v392.ndarray,
                _SequenceV392[float],
            ],
        ],
        *,
        version: str = "1.0",
        description: str = "",
        required_columns: _OptionalV392[
            _SequenceV392[str]
        ] = None,
        output_column: _OptionalV392[str] = None,
        lookback: int = 0,
        horizon: int = 1,
        scope: FactorScopeV392 = FactorScopeV392.CROSS_SECTIONAL,
        direction: FactorDirectionV392 = FactorDirectionV392.NEUTRAL,
        min_obs: int = 1,
        allow_missing: bool = False,
        require_available_date: bool = False,
    ):
        config = FactorConfigV392(
            name=name,
            version=version,
            description=description,
            required_columns=(
                list(required_columns)
                if required_columns is not None
                else []
            ),
            output_column=output_column or name,
            lookback=lookback,
            horizon=horizon,
            scope=scope,
            direction=direction,
            min_obs=min_obs,
            allow_missing=allow_missing,
            require_available_date=require_available_date,
        )
        super().__init__(config)
        self.func = func

    def compute(
        self,
        data: pd.DataFrame,
        context: _OptionalV392[FactorContextV392] = None,
    ):
        return self.func(data, context)


# ----------------------------------------------------------------------------
# Utility Functions
# ----------------------------------------------------------------------------
def ensure_factor_frame_v392(
    data: pd.DataFrame,
    factors: _UnionV392[
        FactorResultV392,
        _MappingV392[str, FactorResultV392],
        _SequenceV392[FactorResultV392],
    ],
) -> pd.DataFrame:
    """将一个或多个 FactorResult 合并到 DataFrame。"""
    if not isinstance(data, pd.DataFrame):
        raise FactorInputErrorV392(
            "data must be pandas.DataFrame."
        )
    result = data.copy()
    if isinstance(factors, FactorResultV392):
        factors = [factors]
    elif isinstance(factors, _MappingV392):
        factors = list(factors.values())
    if not isinstance(factors, _SequenceV392):
        raise FactorInputErrorV392(
            "factors must be FactorResult, mapping, or sequence."
        )
    for factor_result in factors:
        if not isinstance(factor_result, FactorResultV392):
            raise FactorInputErrorV392(
                "All factor outputs must be FactorResult."
            )
        series = factor_result.data
        if not series.index.equals(result.index):
            series = series.reindex(result.index)
        result[factor_result.name] = series
    return result


def factor_metadata_v392(
    factor: BaseFactorV392,
) -> _DictV392[str, _AnyV392]:
    """获取因子 metadata（Experiment Registry 用）。"""
    if not isinstance(factor, BaseFactorV392):
        raise FactorErrorV392(
            "factor must inherit from BaseFactorV392."
        )
    return factor.get_metadata()


# ----------------------------------------------------------------------------
# Example Factor（20 日动量示例，仅用于演示 API）
# ----------------------------------------------------------------------------
class ExampleMomentumFactorV392(BaseFactorV392):
    """示例：N 日价格动量。真正技术因子会放到 factors/technical.py。"""

    def __init__(self, window: int = 20):
        config = FactorConfigV392(
            name=f"momentum_{window}",
            version="1.0",
            description=f"{window}日价格动量",
            required_columns=["code", "date", "close"],
            output_column=f"momentum_{window}",
            lookback=window,
            horizon=1,
            scope=FactorScopeV392.TIME_SERIES,
            direction=FactorDirectionV392.POSITIVE,
            min_obs=1,
            allow_nan_output=True,
        )
        super().__init__(config)
        self.window = window

    def compute(
        self,
        data: pd.DataFrame,
        context: _OptionalV392[FactorContextV392] = None,
    ) -> pd.Series:
        df = data.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["close"] = pd.to_numeric(
            df["close"], errors="coerce"
        )
        df["_original_index"] = _np_v392.arange(len(df))
        df = df.sort_values(["code", "date"])
        momentum = df.groupby("code")["close"].transform(
            lambda x: x / x.shift(self.window) - 1.0
        )
        momentum.index = df.index
        restored = (
            pd.DataFrame(
                {
                    "_original_index": df["_original_index"],
                    "value": momentum,
                }
            ).sort_values("_original_index")
        )
        restored.index = data.index
        return restored["value"]
