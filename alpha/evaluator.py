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
