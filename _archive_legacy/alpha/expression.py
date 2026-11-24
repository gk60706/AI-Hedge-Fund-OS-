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

# ============================================================
# V3.9.2 Alpha Expression (appended, V392 suffix)
# 与 legacy AlphaExpression 语义不同：frozen dataclass、children tuple、
# feature/value/operator 三选一校验、canonical/to_dict/validate。
# 为避免覆盖 legacy 同名类，V392 版命名为 AlphaExpressionV392。
# ============================================================

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

MAX_EXPRESSION_DEPTH = 12
MAX_EXPRESSION_NODES = 64


@dataclass(frozen=True)
class AlphaExpressionV392:
    """
    Alpha 表达式树节点（V3.9.2）。

    三种基本节点：

    1. feature
    2. constant
    3. operator
    """
    operator: Optional[str] = None
    children: tuple["AlphaExpressionV392", ...] = field(default_factory=tuple)
    value: Optional[float] = None
    feature: Optional[str] = None
# --------------------------------------------------------
# Validation
# --------------------------------------------------------
    def __post_init__(self) -> None:
        operator = (self.operator.lower().strip() if self.operator else None)
        feature = (self.feature.strip() if self.feature else None)
        if operator is not None:
            object.__setattr__(self, "operator", operator)
            if feature is not None:
                object.__setattr__(self, "feature", feature)
                if self.children is None:
                    object.__setattr__(self, "children", tuple())
                elif not isinstance(self.children, tuple):
                    object.__setattr__(self, "children", tuple(self.children))
                node_types = sum([
                    self.operator is not None,
                    self.feature is not None,
                    self.value is not None,
                ])
                if node_types != 1:
                    raise ValueError(
                        "AlphaExpressionV392 must represent exactly one of: operator, feature, or value."
                    )
                if self.operator is None and self.children:
                    raise ValueError("Feature/constant nodes cannot have children.")
                if self.operator is not None:
                    if not self.operator:
                        raise ValueError("Operator cannot be empty.")
                    for child in self.children:
                        if not isinstance(child, AlphaExpressionV392):
                            raise TypeError(
                                "All expression children must be AlphaExpressionV392 instances."
                            )
                        if self.value is not None:
                            try:
                                numeric_value = float(self.value)
                            except (TypeError, ValueError) as exc:
                                raise ValueError(
                                    f"Expression constant must be numeric: {self.value}"
                                ) from exc
                            object.__setattr__(self, "value", numeric_value)
# --------------------------------------------------------
# Constructors
# --------------------------------------------------------
    @classmethod
    def feature_node(cls, name: str) -> "AlphaExpressionV392":
        return cls(feature=str(name))

    @classmethod
    def constant(cls, value: float) -> "AlphaExpressionV392":
        return cls(value=float(value))

    @classmethod
    def op(cls, operator: str, *children: "AlphaExpressionV392") -> "AlphaExpressionV392":
        return cls(operator=operator, children=tuple(children))
# --------------------------------------------------------
# Properties
# --------------------------------------------------------
    @property
    def is_feature(self) -> bool:
        return self.feature is not None

    @property
    def is_constant(self) -> bool:
        return self.value is not None

    @property
    def is_operator(self) -> bool:
        return self.operator is not None

    @property
    def root_operator(self) -> Optional[str]:
        return self.operator
# --------------------------------------------------------
# Tree information
# --------------------------------------------------------
    def node_count(self) -> int:
        """
        表达式节点数量。

        """
        if not self.children:
            return 1
        return 1 + sum(child.node_count() for child in self.children)

    def depth(self) -> int:
        """
        表达式树深度。

        leaf depth = 1

        """
        if not self.children:
            return 1
        return 1 + max(child.depth() for child in self.children)

    def feature_names(self) -> tuple[str, ...]:
        """
        返回表达式涉及的全部 feature。

        """
        result: set[str] = set()
        self._collect_features(result)
        return tuple(sorted(result))

    def _collect_features(self, output: set[str]) -> None:
        if self.feature is not None:
            output.add(self.feature)
            return
        for child in self.children:
            child._collect_features(output)

    def constants(self) -> tuple[float, ...]:
        result: list[float] = []
        self._collect_constants(result)
        return tuple(result)

    def _collect_constants(self, output: list[float]) -> None:
        if self.value is not None:
            output.append(float(self.value))
            return
        for child in self.children:
            child._collect_constants(output)
# --------------------------------------------------------
# String representation
# --------------------------------------------------------
    def to_string(self) -> str:
        """
        人类可读表达式。

        例如：

        add(roe,momentum_20)

        """
        if self.feature is not None:
            return self.feature
        if self.value is not None:
            return _format_constant_v392(self.value)
        if self.operator is None:
            raise RuntimeError("Invalid expression node.")
        args = ",".join(child.to_string() for child in self.children)
        return f"{self.operator}({args})"

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"AlphaExpressionV392({self.to_string()})"
# --------------------------------------------------------
# Canonical representation
# --------------------------------------------------------
    def canonical(self) -> str:
        """
        返回用于去重的 canonical expression。

        对 add / mul 等交换律操作进行标准化。

        """
        if self.feature is not None:
            return f"feature:{self.feature}"
        if self.value is not None:
            return f"constant:{_format_constant_v392(self.value)}"
        children = [child.canonical() for child in self.children]
        if self.operator in {"add", "mul"}:
            children.sort()
            return f"op:{self.operator}(" + ",".join(children) + ")"
        return f"op:{self.operator}(" + ",".join(children) + ")"
# --------------------------------------------------------
# Serialization
# --------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        if self.feature is not None:
            return {"type": "feature", "feature": self.feature}
        if self.value is not None:
            return {"type": "constant", "value": float(self.value)}
        return {
            "type": "operator",
            "operator": self.operator,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AlphaExpressionV392":
        if not isinstance(data, dict):
            raise TypeError("Expression data must be a dict.")
        node_type = data.get("type")
        if node_type == "feature":
            return cls.feature_node(data["feature"])
        if node_type == "constant":
            return cls.constant(data["value"])
        if node_type == "operator":
            children = tuple(cls.from_dict(child) for child in data.get("children", []))
            return cls(operator=data["operator"], children=children)
        raise ValueError(f"Unknown expression node type: {node_type}")
# --------------------------------------------------------
# Validation
# --------------------------------------------------------
    def validate(self, *, max_depth: int = MAX_EXPRESSION_DEPTH,
                 max_nodes: int = MAX_EXPRESSION_NODES) -> None:
        """
        验证表达式树是否合法。

        """
        if self.depth() > max_depth:
            raise ValueError(
                f"Expression depth {self.depth()} exceeds max_depth={max_depth}."
            )
        if self.node_count() > max_nodes:
            raise ValueError(
                f"Expression node count {self.node_count()} exceeds max_nodes={max_nodes}."
            )
        if self.feature is not None:
            if not self.feature.strip():
                raise ValueError("Feature name cannot be empty.")
            for child in self.children:
                child.validate(max_depth=max_depth, max_nodes=max_nodes)
# --------------------------------------------------------
# Replace
# --------------------------------------------------------
    def replace_child(self, index: int, replacement: "AlphaExpressionV392") -> "AlphaExpressionV392":
        if not self.is_operator:
            raise ValueError("Only operator nodes can replace children.")
        if index < 0 or index >= len(self.children):
            raise IndexError("Child index out of range.")
        children = list(self.children)
        children[index] = replacement
        return AlphaExpressionV392(operator=self.operator, children=tuple(children))
# ============================================================
# V392 helpers
# ============================================================
def _format_constant_v392(value: float) -> str:
    value = float(value)
    if value == 0:
        return "0"
    if value.is_integer():
        return str(int(value))
    return f"{value:.8g}"


def feature(name: str) -> AlphaExpressionV392:
    return AlphaExpressionV392.feature_node(name)


def constant(value: float) -> AlphaExpressionV392:
    return AlphaExpressionV392.constant(value)


def operation(operator: str, *children: AlphaExpressionV392) -> AlphaExpressionV392:
    return AlphaExpressionV392.op(operator, *children)


def expression_from_dict(data: dict[str, Any]) -> AlphaExpressionV392:
    return AlphaExpressionV392.from_dict(data)


__all__ = [
    "AlphaExpressionV392",
    "MAX_EXPRESSION_DEPTH",
    "MAX_EXPRESSION_NODES",
    "feature",
    "constant",
    "operation",
    "expression_from_dict",
]

