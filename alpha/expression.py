from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlphaExpression:
    operator: str
    children: list[Any] = field(default_factory=list)
    value: float | None = None
    feature: str | None = None

    def complexity(self) -> int:
        score = 1
        for child in self.children:
            if isinstance(child, AlphaExpression):
                score += child.complexity()
        return score

    def to_string(self) -> str:
        if self.feature:
            return self.feature
        if self.operator == "CONST":
            return str(round(self.value or 0, 4))
        if self.operator in {"NEG", "ABS", "LOG", "RANK", "ZSCORE"}:
            child = self.children[0].to_string()
            return f"{self.operator}({child})"
        if len(self.children) == 2:
            left = self.children[0].to_string()
            right = self.children[1].to_string()
            return f"({left} {self.operator} {right})"
        return self.operator


# ============================================================================
# V3.9.1 unified research engine - expression with constant support
# ============================================================================


@dataclass
class AlphaExpressionV391:
    operator: str = ""
    children: list[Any] = field(default_factory=list)
    feature: str | None = None
    constant: float | None = None

    @staticmethod
    def feature_node(feature: str) -> "AlphaExpressionV391":
        return AlphaExpressionV391(feature=feature)

    @staticmethod
    def const(value: float) -> "AlphaExpressionV391":
        return AlphaExpressionV391(constant=value)

    def is_leaf(self) -> bool:
        return self.feature is not None or self.constant is not None

    def complexity(self) -> int:
        if self.is_leaf():
            return 1
        return 1 + sum(
            child.complexity()
            for child in self.children
            if isinstance(child, AlphaExpressionV391)
        )

    def to_string(self) -> str:
        if self.constant is not None:
            return str(self.constant)
        if self.feature is not None:
            return self.feature
        parts = [child.to_string() for child in self.children]
        return f"({self.operator} {' '.join(parts)})"
