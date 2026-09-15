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
