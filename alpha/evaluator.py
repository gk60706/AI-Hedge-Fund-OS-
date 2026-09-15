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
