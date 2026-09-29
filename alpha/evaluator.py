from __future__ import annotations

import pandas as pd

from alpha.expression import AlphaExpression
from alpha.operators import AlphaOperators


class AlphaEvaluator:
    def evaluate(
        self,
        expression: AlphaExpression,
        features: pd.DataFrame,
    ) -> pd.Series:
        if expression.feature:
            if expression.feature not in features:
                raise ValueError(
                    f"不存在因子: {expression.feature}"
                )
            return features[expression.feature].copy()
        if expression.operator == "CONST":
            return pd.Series(
                expression.value,
                index=features.index,
            )
        children = [
            self.evaluate(child, features)
            for child in expression.children
        ]
        operator = expression.operator
        if operator == "ADD":
            return AlphaOperators.add(children[0], children[1])
        if operator == "SUB":
            return AlphaOperators.sub(children[0], children[1])
        if operator == "MUL":
            return AlphaOperators.mul(children[0], children[1])
        if operator == "DIV":
            return AlphaOperators.div(children[0], children[1])
        if operator == "NEG":
            return AlphaOperators.neg(children[0])
        if operator == "ABS":
            return AlphaOperators.abs(children[0])
        if operator == "LOG":
            return AlphaOperators.log(children[0])
        if operator == "RANK":
            return AlphaOperators.rank(children[0])
        if operator == "ZSCORE":
            return AlphaOperators.zscore(children[0])
        raise ValueError(f"未知 operator: {operator}")
# ============================================================================
# V3.9.1 unified research engine - expression evaluator (V391 tree, dump semantics)
# ============================================================================


class ExpressionEvaluator:
    def evaluate(self, expression, df):
        if expression.feature is not None:
            if expression.feature not in df.columns:
                return pd.Series(float("nan"), index=df.index)
            return pd.to_numeric(df[expression.feature], errors="coerce")
        if expression.constant is not None:
            return pd.Series(float(expression.constant), index=df.index)
        args = [self.evaluate(child, df) for child in expression.children]
        return apply_operator_v391(expression.operator, args, df["date"])


from alpha.operators import apply_operator_v391  # noqa: E402

# ============================================================
# V3.9.2 Alpha Expression Evaluator (appended, V392)
# ============================================================

import numpy as np
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

from alpha.expression import AlphaExpressionV392
from alpha.operators import get_operator, get_operator_arity
# ============================================================
# V392 constants
# ============================================================
DEFAULT_DATE_COLUMN = "date"
DEFAULT_CODE_COLUMN = "code"
# ============================================================
# V392 exceptions
# ============================================================
class AlphaEvaluationError(RuntimeError):
    """Alpha expression evaluation error."""


class MissingFeatureError(AlphaEvaluationError):
    """Expression requires unavailable feature."""
# ============================================================
# V392 evaluation config
# ============================================================
@dataclass(frozen=True)
class AlphaEvaluationConfig:
    """
    Alpha Evaluation 参数（V3.9.2）。

    """
    date_column: str = DEFAULT_DATE_COLUMN
    code_column: str = DEFAULT_CODE_COLUMN
    drop_non_finite: bool = True
    preserve_index: bool = True
    validate_expression: bool = True
    max_depth: int = 12
    max_nodes: int = 64
# ============================================================
# V392 evaluator
# ============================================================
class AlphaExpressionEvaluator:
    """
    AlphaExpressionV392 evaluator（V3.9.2）。

    示例：

        evaluator = AlphaExpressionEvaluator()

        signal = evaluator.evaluate(expression, df)

    """
    def __init__(self, config: Optional[AlphaEvaluationConfig] = None) -> None:
        self.config = (config or AlphaEvaluationConfig())
# --------------------------------------------------------
# V392 public
# --------------------------------------------------------
    def evaluate(self, expression: AlphaExpressionV392, data: pd.DataFrame) -> pd.Series:
        """
        计算单个 AlphaExpressionV392。

        """
        if not isinstance(expression, AlphaExpressionV392):
            raise TypeError("expression must be AlphaExpressionV392.")
        if not isinstance(data, pd.DataFrame):
            raise TypeError("data must be pandas.DataFrame.")
        if self.config.validate_expression:
            expression.validate(
                max_depth=self.config.max_depth,
                max_nodes=self.config.max_nodes,
            )
            missing = [
                feature
                for feature in expression.feature_names()
                if feature not in data.columns
            ]
            if missing:
                raise MissingFeatureError(
                    "Missing expression features: " + ", ".join(missing)
                )
        result = self._evaluate_node(expression, data)
        result = self._sanitize(result)
        if not self.config.preserve_index:
            result = result.reset_index(drop=True)
        return result.rename(expression.to_string())
# --------------------------------------------------------
# V392 batch evaluation
# --------------------------------------------------------
    def evaluate_many(
        self,
        expressions: Sequence[AlphaExpressionV392],
        data: pd.DataFrame,
        *,
        prefix: str = "alpha",
    ) -> pd.DataFrame:
        """
        批量计算 Alpha。

        """
        result: dict[str, pd.Series] = {}
        for index, expression in enumerate(expressions):
            signal = self.evaluate(expression, data)
            name = (expression.to_string())
            if name in result:
                name = (f"{prefix}_{index}")
            result[name] = signal
        if not result:
            return pd.DataFrame(index=data.index)
        return pd.DataFrame(result, index=data.index)
# --------------------------------------------------------
# V392 functional alias
# --------------------------------------------------------
    def __call__(self, expression: AlphaExpressionV392, data: pd.DataFrame) -> pd.Series:
        return self.evaluate(expression, data)
# --------------------------------------------------------
# V392 recursive evaluation
# --------------------------------------------------------
    def _evaluate_node(
        self,
        expression: AlphaExpressionV392,
        data: pd.DataFrame,
    ) -> pd.Series:
# ----------------------------------------------------
# Feature
# ----------------------------------------------------
        if expression.feature is not None:
            series = pd.to_numeric(data[expression.feature], errors="coerce")
            return series.astype("float64")
# ----------------------------------------------------
# Constant
# ----------------------------------------------------
        if expression.value is not None:
            return pd.Series(
                float(expression.value), index=data.index, dtype="float64"
            )
# ----------------------------------------------------
# Operator
# ----------------------------------------------------
        if expression.operator is None:
            raise AlphaEvaluationError(
                "Invalid AlphaExpressionV392: no feature, constant, or operator."
            )
        operator_name = (expression.operator)
        try:
            function = get_operator(operator_name)
        except KeyError as exc:
            raise AlphaEvaluationError(f"Unknown operator: {operator_name}") from exc
        expected_arity = (get_operator_arity(operator_name))
        if (isinstance(expected_arity, int)
                and len(expression.children) != expected_arity):
            raise AlphaEvaluationError(
                f"Operator '{operator_name}' expects {expected_arity} "
                f"children, got {len(expression.children)}."
            )
        child_values = [
            self._evaluate_node(child, data)
            for child in expression.children
        ]
# ----------------------------------------------------
# Cross-sectional operators
# ----------------------------------------------------
        if operator_name in {"rank", "zscore", "winsorize"}:
            if not child_values:
                raise AlphaEvaluationError(
                    f"Operator '{operator_name}' requires one child."
                )
            dates = self._get_dates(data)
            return function(child_values[0], dates)
# ----------------------------------------------------
# Standard operators
# ----------------------------------------------------
        try:
            return function(*child_values)
        except Exception as exc:
            raise AlphaEvaluationError(
                f"Failed to evaluate {expression.to_string()}: {exc}"
            ) from exc
# --------------------------------------------------------
# V392 dates
# --------------------------------------------------------
    def _get_dates(self, data: pd.DataFrame) -> Optional[pd.Series]:
        if (self.config.date_column not in data.columns):
            return None
        return pd.to_datetime(data[self.config.date_column], errors="coerce")
# --------------------------------------------------------
# V392 sanitization
# --------------------------------------------------------
    def _sanitize(self, series: pd.Series) -> pd.Series:
        result = pd.to_numeric(series, errors="coerce").astype("float64")
        result = result.replace([np.inf, -np.inf], np.nan)
        if self.config.drop_non_finite:
            return result
        return result
# ============================================================
# V392 functional API
# ============================================================
def evaluate_expression(
    expression: AlphaExpressionV392,
    data: pd.DataFrame,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    code_column: str = DEFAULT_CODE_COLUMN,
    drop_non_finite: bool = True,
) -> pd.Series:
    """
    V3.9.2 标准函数接口。

    与 alpha/search.py 对接：

        signal = evaluate_expression(expression, panel)

    """
    evaluator = AlphaExpressionEvaluator(
        AlphaEvaluationConfig(
            date_column=date_column,
            code_column=code_column,
            drop_non_finite=drop_non_finite,
        )
    )
    return evaluator.evaluate(expression, data)


def evaluate_expressions(
    expressions: Sequence[AlphaExpressionV392],
    data: pd.DataFrame,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    code_column: str = DEFAULT_CODE_COLUMN,
) -> pd.DataFrame:
    """
    批量计算表达式。

    """
    evaluator = AlphaExpressionEvaluator(
        AlphaEvaluationConfig(
            date_column=date_column,
            code_column=code_column,
        )
    )
    return evaluator.evaluate_many(expressions, data)
# ============================================================
# V392 convenience validation
# ============================================================
def required_features(expression: AlphaExpressionV392) -> tuple[str, ...]:
    """
    返回 expression 需要的 feature。

    """
    return expression.feature_names()


def validate_expression_data(
    expression: AlphaExpressionV392,
    data: pd.DataFrame,
) -> None:
    """
    在正式 evaluation 前检查 DataFrame。

    """
    if not isinstance(expression, AlphaExpressionV392):
        raise TypeError("expression must be AlphaExpressionV392.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be pandas.DataFrame.")
    missing = [
        feature
        for feature in expression.feature_names()
        if feature not in data.columns
    ]
    if missing:
        raise MissingFeatureError("Missing features: " + ", ".join(missing))
# ============================================================
# V392 public exports
# ============================================================
__all__ = [
    "AlphaEvaluationConfig", "AlphaEvaluationError", "MissingFeatureError",
    "AlphaExpressionEvaluator", "evaluate_expression", "evaluate_expressions",
    "required_features", "validate_expression_data",
]

