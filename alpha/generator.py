from __future__ import annotations

import random

from alpha.expression import AlphaExpression

FEATURES = [
    "pe_inverse",
    "pb_inverse",
    "ps_inverse",
    "momentum_20",
    "momentum_60",
    "momentum_120",
    "roe",
    "roic",
    "revenue_growth",
    "profit_growth",
    "volatility_20",
    "turnover",
    "amount_20",
]

BINARY_OPERATORS = ["ADD", "SUB", "MUL", "DIV"]
UNARY_OPERATORS = ["NEG", "ABS", "LOG", "RANK", "ZSCORE"]


class AlphaGenerator:
    def random_leaf(self):
        if random.random() < 0.9:
            return AlphaExpression(
                operator="FEATURE",
                feature=random.choice(FEATURES),
            )
        return AlphaExpression(
            operator="CONST",
            value=random.uniform(-1, 1),
        )

    def generate(self, depth=2):
        if depth <= 0:
            return self.random_leaf()
        probability = random.random()
        if probability < 0.45:
            operator = random.choice(BINARY_OPERATORS)
            return AlphaExpression(
                operator=operator,
                children=[
                    self.generate(depth - 1),
                    self.generate(depth - 1),
                ],
            )
        operator = random.choice(UNARY_OPERATORS)
        return AlphaExpression(
            operator=operator,
            children=[self.generate(depth - 1)],
        )

    def generate_population(self, size=100, max_depth=3):
        return [
            self.generate(random.randint(1, max_depth))
            for _ in range(size)
        ]


# ============================================================================
# V3.9.1 unified research engine - generator for panel-compatible features
# ============================================================================

FEATURES_V391 = [
    "value",
    "momentum",
    "quality",
    "volatility",
    "liquidity",
    "turnover",
    "pe",
    "pb",
]


class AlphaGeneratorV391:
    def __init__(self, seed: int = 42, max_depth: int = 3):
        self.random = random.Random(seed)
        self.max_depth = max_depth

    def _leaf(self):
        return AlphaExpressionV391.feature_node(
            self.random.choice(FEATURES_V391)
        )

    def generate(self, depth: int = 1) -> AlphaExpressionV391:
        if depth >= self.max_depth or self.random.random() < 0.4:
            return self._leaf()
        operator = self.random.choice(BINARY_OPERATORS)
        left = self.generate(depth + 1)
        right = self.generate(depth + 1)
        return AlphaExpressionV391(
            operator=operator,
            children=[left, right],
        )
from alpha.expression import AlphaExpressionV391

# ============================================================
# V3.9.2 Alpha Expression Generator (appended, V392)
# 注意：legacy 已有 class AlphaGenerator（V391 前），
# V392 提供 AlphaExpressionGenerator + AlphaGeneratorV392 别名。
# ============================================================

import random
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from alpha.expression import (
    AlphaExpressionV392, MAX_EXPRESSION_DEPTH, MAX_EXPRESSION_NODES,
)
from alpha.operators import (
    OPERATOR_ARITY, is_binary_operator, is_unary_operator,
)
# ============================================================
# V392 default feature universe
# ============================================================
DEFAULT_FEATURES_V392: tuple[str, ...] = (
    "pe_inverse", "pb_inverse", "ps_inverse",
    "momentum_20", "momentum_60", "momentum_120",
    "roe", "roic", "revenue_growth", "profit_growth",
    "volatility_20", "turnover", "amount_20",
)
DEFAULT_UNARY_OPERATORS_V392: tuple[str, ...] = (
    "neg", "abs", "sign", "log", "sqrt", "inv", "rank", "zscore"
)
DEFAULT_BINARY_OPERATORS_V392: tuple[str, ...] = ("add", "sub", "mul", "div")
DEFAULT_CONSTANTS_V392: tuple[float, ...] = (-2.0, -1.0, -0.5, 0.5, 1.0, 2.0)
# ============================================================
# V392 generator config
# ============================================================
@dataclass(frozen=True)
class AlphaGeneratorConfig:
    """
    Alpha Generator 参数（V3.9.2）。

    """
    features: tuple[str, ...] = DEFAULT_FEATURES_V392
    unary_operators: tuple[str, ...] = (DEFAULT_UNARY_OPERATORS_V392)
    binary_operators: tuple[str, ...] = (DEFAULT_BINARY_OPERATORS_V392)
    constants: tuple[float, ...] = (DEFAULT_CONSTANTS_V392)
    max_depth: int = 4
    max_nodes: int = 15
    constant_probability: float = 0.10
    unary_probability: float = 0.45
    binary_probability: float = 0.45
    seed: Optional[int] = 42
    include_base_features: bool = True
    deduplicate: bool = True

    def __post_init__(self) -> None:
        if not self.features:
            raise ValueError("features cannot be empty.")
        if self.max_depth < 1:
            raise ValueError("max_depth must be >= 1.")
        if self.max_nodes < 1:
            raise ValueError("max_nodes must be >= 1.")
        total_probability = (
            self.constant_probability
            + self.unary_probability
            + self.binary_probability
        )
        if total_probability <= 0:
            raise ValueError("Operator probabilities must sum to a positive number.")
        for value in (self.constant_probability, self.unary_probability,
                      self.binary_probability):
            if value < 0:
                raise ValueError("Probabilities cannot be negative.")
# ============================================================
# V392 generator
# ============================================================
class AlphaExpressionGenerator:
    """
    随机 Alpha Expression Generator（V3.9.2）。

    示例：

        config = AlphaGeneratorConfig(
            max_depth=4,
            max_nodes=15,
            seed=42,
        )

        generator = AlphaExpressionGenerator(config)

        candidates = generator.generate_candidates(100)

    """
    def __init__(self, config: Optional[AlphaGeneratorConfig] = None) -> None:
        self.config = (config or AlphaGeneratorConfig())
        self.random = random.Random(self.config.seed)
        self._validate_config()
# --------------------------------------------------------
# V392 public
# --------------------------------------------------------
    def generate(self) -> AlphaExpressionV392:
        """
        生成一个 AlphaExpressionV392。

        """
        expression = self._generate_node(depth=1)
        expression.validate(
            max_depth=self.config.max_depth,
            max_nodes=self.config.max_nodes,
        )
        return expression

    def generate_candidates(
        self,
        n: int,
        *,
        include_base_features: Optional[bool] = None,
        deduplicate: Optional[bool] = None,
    ) -> list[AlphaExpressionV392]:
        """
        生成 n 个候选 Alpha。

        与 alpha/search.py 保持兼容：

            generate_candidates(n)

        """
        if n <= 0:
            return []
        include_base = (
            self.config.include_base_features
            if include_base_features is None
            else include_base_features
        )
        should_deduplicate = (
            self.config.deduplicate if deduplicate is None else deduplicate
        )
        results: list[AlphaExpressionV392] = []
        seen: set[str] = set()
        if include_base:
            for feature_name in (self.config.features):
                expression = (AlphaExpressionV392.feature_node(feature_name))
                canonical = (expression.canonical())
                if (not should_deduplicate or canonical not in seen):
                    results.append(expression)
                    seen.add(canonical)
                    if len(results) >= n:
                        return results[:n]
        attempts = 0
        max_attempts = max(n * 30, 100)
        while (len(results) < n and attempts < max_attempts):
            attempts += 1
            try:
                expression = self.generate()
            except (ValueError, RecursionError):
                continue
            canonical = (expression.canonical())
            if (should_deduplicate and canonical in seen):
                continue
            seen.add(canonical)
            results.append(expression)
        return results[:n]
# --------------------------------------------------------
# V392 compatibility aliases
# --------------------------------------------------------
    def generate_many(self, n: int) -> list[AlphaExpressionV392]:
        return self.generate_candidates(n)
# --------------------------------------------------------
# V392 internal generation
# --------------------------------------------------------
    def _generate_node(self, depth: int) -> AlphaExpressionV392:
        """
        递归生成 expression。

        """
        if depth >= self.config.max_depth:
            return self._generate_leaf()
        if (depth > 1 and self.random.random() < 0.35):
            return self._generate_leaf()
        choice = self._choose_node_type()
        if choice == "constant":
            return self._generate_constant()
        if choice == "unary":
            operator = self.random.choice(self.config.unary_operators)
            child = self._generate_node(depth + 1)
            return AlphaExpressionV392(operator=operator, children=(child,))
        if choice == "binary":
            operator = self.random.choice(self.config.binary_operators)
            left = self._generate_node(depth + 1)
            right = self._generate_node(depth + 1)
            return AlphaExpressionV392(operator=operator, children=(left, right))
        return self._generate_feature()

    def _generate_leaf(self) -> AlphaExpressionV392:
        """
        叶节点优先生成 feature。

        """
        if (self.config.constants
                and self.random.random() < self.config.constant_probability):
            return self._generate_constant()
        return self._generate_feature()

    def _generate_feature(self) -> AlphaExpressionV392:
        return AlphaExpressionV392.feature_node(
            self.random.choice(self.config.features)
        )

    def _generate_constant(self) -> AlphaExpressionV392:
        if not self.config.constants:
            return AlphaExpressionV392.constant(1.0)
        return AlphaExpressionV392.constant(
            self.random.choice(self.config.constants)
        )

    def _choose_node_type(self) -> str:
        """
        根据概率选择节点类型。

        """
        p_constant = max(0.0, self.config.constant_probability)
        p_unary = max(0.0, self.config.unary_probability)
        p_binary = max(0.0, self.config.binary_probability)
        total = (p_constant + p_unary + p_binary)
        if total <= 0:
            return "feature"
        value = (self.random.random() * total)
        if value < p_constant:
            return "constant"
        value -= p_constant
        if value < p_unary:
            return "unary"
        value -= p_unary
        if value < p_binary:
            return "binary"
        return "feature"
# --------------------------------------------------------
# V392 validation
# --------------------------------------------------------
    def _validate_config(self) -> None:
        if self.config.max_depth > (MAX_EXPRESSION_DEPTH):
            raise ValueError(f"max_depth cannot exceed {MAX_EXPRESSION_DEPTH}.")
        if self.config.max_nodes > (MAX_EXPRESSION_NODES):
            raise ValueError(f"max_nodes cannot exceed {MAX_EXPRESSION_NODES}.")
        for operator in (self.config.unary_operators):
            if not is_unary_operator(operator):
                raise ValueError(f"Operator '{operator}' is not unary.")
        for operator in (self.config.binary_operators):
            if not is_binary_operator(operator):
                raise ValueError(f"Operator '{operator}' is not binary.")
# ============================================================
# V392 functional API
# ============================================================
def generate_candidates(
    n: int,
    *,
    features: Optional[Sequence[str]] = None,
    max_depth: int = 4,
    max_nodes: int = 15,
    seed: Optional[int] = 42,
    deduplicate: bool = True,
) -> list[AlphaExpressionV392]:
    """
    与 alpha/search.py 兼容的函数式接口。

    示例：

        candidates = generate_candidates(
            100,
            features=[
                "roe",
                "momentum_20",
            ],
            seed=42,
        )

    """
    config = AlphaGeneratorConfig(
        features=tuple(features or DEFAULT_FEATURES_V392),
        max_depth=max_depth,
        max_nodes=max_nodes,
        seed=seed,
        deduplicate=deduplicate,
    )
    generator = AlphaExpressionGenerator(config)
    return generator.generate_candidates(n)
# ============================================================
# V392 default alias
# ============================================================
AlphaGeneratorV392 = AlphaExpressionGenerator

__all__ = [
    "AlphaGeneratorConfig", "AlphaExpressionGenerator", "AlphaGeneratorV392",
    "DEFAULT_FEATURES_V392", "DEFAULT_UNARY_OPERATORS_V392",
    "DEFAULT_BINARY_OPERATORS_V392", "DEFAULT_CONSTANTS_V392",
    "generate_candidates",
]

