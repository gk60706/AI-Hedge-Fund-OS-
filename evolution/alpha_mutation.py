from __future__ import annotations

import random

from alpha.expression import AlphaExpression
from alpha.generator import (
    FEATURES,
    BINARY_OPERATORS,
    UNARY_OPERATORS,
)


class AlphaMutation:
    def mutate(self, expression, probability=0.20):
        if random.random() > probability:
            return expression
        return self._mutate_node(expression)

    def _mutate_node(self, node):
        if random.random() < 0.25:
            return AlphaExpression(
                operator="FEATURE",
                feature=random.choice(FEATURES),
            )
        if node.children and random.random() < 0.6:
            index = random.randrange(len(node.children))
            node.children[index] = self._mutate_node(
                node.children[index]
            )
            return node
        if node.operator in (BINARY_OPERATORS):
            node.operator = random.choice(BINARY_OPERATORS)
        elif node.operator in (UNARY_OPERATORS):
            node.operator = random.choice(UNARY_OPERATORS)
        return node

# ============================================================

# ============================================================
# V3.9.3 Alpha Mutation Engine (appended)
# 旧版 AlphaMutation（legacy）保留；以下为 V3.9.3 新引擎。
# expression 使用项目的 V3.9.2 实现 AlphaExpressionV392，
# genome 使用 V3.9.3 的 AlphaGenomeV393。
# ============================================================

from dataclasses import dataclass, field
from typing import Optional, Sequence, Any
import math
import random

from alpha.expression import AlphaExpressionV392 as _AMExpr
from alpha.operators import (
    OPERATORS,
    get_operator_arity,
    is_binary_operator,
    is_unary_operator,
)
from evolution.alpha_genome import (
    AlphaGenomeV393 as _AMGenome,
)
# ============================================================
# Constants
# ============================================================
DEFAULT_FEATURES: tuple[str, ...] = (
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
)
DEFAULT_UNARY_OPERATORS: tuple[str, ...] = (
    "neg",
    "abs",
    "sign",
    "log",
    "sqrt",
    "inv",
    "rank",
    "zscore",
)
DEFAULT_BINARY_OPERATORS: tuple[str, ...] = (
    "add",
    "sub",
    "mul",
    "div",
)
DEFAULT_CONSTANTS: tuple[float, ...] = (
    -2.0,
    -1.0,
    -0.5,
    0.5,
    1.0,
    2.0,
)
DEFAULT_MUTATION_TYPES: tuple[str, ...] = (
    "feature_mutation",
    "constant_mutation",
    "operator_mutation",
    "subtree_mutation",
    "unary_insert",
    "unary_delete",
    "child_replace",
)
# ============================================================
# Exceptions
# ============================================================
class AlphaMutationError(Exception):
    """Alpha Mutation 基础异常。"""
class InvalidMutationError(AlphaMutationError):
    """Mutation 参数非法。"""
class MutationConstraintError(AlphaMutationError):
    """Mutation 后表达式违反深度/节点限制。"""
# ============================================================
# Mutation configuration
# ============================================================
@dataclass(frozen=True)
class AlphaMutationConfig:
    """
    Alpha Mutation 配置。
    """
    features: tuple[str, ...] = DEFAULT_FEATURES
    unary_operators: tuple[str, ...] = (
        DEFAULT_UNARY_OPERATORS
    )
    binary_operators: tuple[str, ...] = (
        DEFAULT_BINARY_OPERATORS
    )
    constants: tuple[float, ...] = (
        DEFAULT_CONSTANTS
    )
    # --------------------------------------------------------
    # Expression constraints
    # --------------------------------------------------------
    max_depth: int = 4
    max_nodes: int = 15
    # --------------------------------------------------------
    # Mutation probability
    # --------------------------------------------------------
    feature_probability: float = 0.20
    constant_probability: float = 0.10
    operator_probability: float = 0.15
    subtree_probability: float = 0.20
    unary_insert_probability: float = 0.15
    unary_delete_probability: float = 0.10
    child_replace_probability: float = 0.10
    # --------------------------------------------------------
    # Subtree generation
    # --------------------------------------------------------
    subtree_max_depth: int = 2
    subtree_constant_probability: float = 0.10
    subtree_unary_probability: float = 0.45
    subtree_binary_probability: float = 0.45
    # --------------------------------------------------------
    # Mutation behaviour
    # --------------------------------------------------------
    allow_same_feature: bool = False
    allow_same_operator: bool = False
    allow_same_constant: bool = False
    retry_count: int = 12
    seed: Optional[int] = 42
    def __post_init__(self) -> None:
        """
        校验配置。
        """
        if self.max_depth < 1:
            raise ValueError(
                "max_depth must be >= 1."
            )
        if self.max_nodes < 1:
            raise ValueError(
                "max_nodes must be >= 1."
            )
        if self.subtree_max_depth < 0:
            raise ValueError(
                "subtree_max_depth must be >= 0."
            )
        probabilities = (
            self.feature_probability,
            self.constant_probability,
            self.operator_probability,
            self.subtree_probability,
            self.unary_insert_probability,
            self.unary_delete_probability,
            self.child_replace_probability,
        )
        for probability in probabilities:
            if not 0.0 <= probability <= 1.0:
                raise ValueError(
                    "Mutation probabilities must "
                    "be between 0 and 1."
                )
        if not self.features:
            raise ValueError(
                "features cannot be empty."
            )
        if not self.unary_operators:
            raise ValueError(
                "unary_operators cannot be empty."
            )
        if not self.binary_operators:
            raise ValueError(
                "binary_operators cannot be empty."
            )
        if not self.constants:
            raise ValueError(
                "constants cannot be empty."
            )
        if self.retry_count < 1:
            raise ValueError(
                "retry_count must be >= 1."
            )
# ============================================================
# Utility functions
# ============================================================
def _weighted_mutation_types(
    config: AlphaMutationConfig,
) -> tuple[tuple[str, float], ...]:
    """
    返回 Mutation 类型及其权重。
    """
    return (
        (
            "feature_mutation",
            config.feature_probability,
        ),
        (
            "constant_mutation",
            config.constant_probability,
        ),
        (
            "operator_mutation",
            config.operator_probability,
        ),
        (
            "subtree_mutation",
            config.subtree_probability,
        ),
        (
            "unary_insert",
            config.unary_insert_probability,
        ),
        (
            "unary_delete",
            config.unary_delete_probability,
        ),
        (
            "child_replace",
            config.child_replace_probability,
        ),
    )
def _choose_weighted(
    rng: random.Random,
    items: Sequence[tuple[str, float]],
) -> str:
    """
    根据权重随机选择。
    """
    valid = [
        item
        for item in items
        if item[1] > 0
    ]
    if not valid:
        raise InvalidMutationError(
            "No mutation probability is positive."
        )
    names = [
        item[0]
        for item in valid
    ]
    weights = [
        item[1]
        for item in valid
    ]
    return rng.choices(
        names,
        weights=weights,
        k=1,
    )[0]
def _random_different(
    rng: random.Random,
    values: Sequence[Any],
    current: Any,
) -> Any:
    """
    尽量选择与 current 不同的值。
    """
    values = tuple(values)
    if not values:
        raise ValueError(
            "values cannot be empty."
        )
    if len(values) == 1:
        return values[0]
    candidates = [
        value
        for value in values
        if value != current
    ]
    if candidates:
        return rng.choice(
            candidates
        )
    return rng.choice(
        values
    )
# ============================================================
# Expression tree utilities
# ============================================================
def _collect_nodes(
    expression: _AMExpr,
) -> list[_AMExpr]:
    """
    前序遍历收集所有节点。
    """
    nodes: list[
        _AMExpr
    ] = []
    def visit(
        node: _AMExpr,
    ) -> None:
        nodes.append(node)
        for child in node.children:
            visit(child)
    visit(expression)
    return nodes
def _collect_paths(
    expression: _AMExpr,
) -> list[tuple[int, ...]]:
    """
    返回 Expression Tree 中所有节点的 path。
    例如：
        add(
            roe,
            mul(
                momentum_20,
                pb_inverse
            )
        )
    path:
        ()
        (0,)
        (1,)
        (1,0)
        (1,1)
    """
    paths: list[
        tuple[int, ...]
    ] = []
    def visit(
        node: _AMExpr,
        path: tuple[int, ...],
    ) -> None:
        paths.append(path)
        for index, child in enumerate(
            node.children
        ):
            visit(
                child,
                path + (index,),
            )
    visit(
        expression,
        (),
    )
    return paths
def _get_subtree(
    expression: _AMExpr,
    path: tuple[int, ...],
) -> _AMExpr:
    """
    根据 path 获取 subtree。
    """
    node = expression
    for index in path:
        node = node.children[index]
    return node
def _replace_subtree(
    expression: _AMExpr,
    path: tuple[int, ...],
    replacement: _AMExpr,
) -> _AMExpr:
    """
    替换指定 path 的 subtree。
    不修改原始 expression。
    """
    if not path:
        return replacement
    index = path[0]
    if index >= len(
        expression.children
    ):
        raise IndexError(
            "Invalid expression path."
        )
    new_child = _replace_subtree(
        expression.children[index],
        path[1:],
        replacement,
    )
    children = list(
        expression.children
    )
    children[index] = new_child
    return _AMExpr.op(
        expression.operator,
        *children,
    )
def _expression_at_parent(
    expression: _AMExpr,
    path: tuple[int, ...],
) -> Optional[
    _AMExpr
]:
    """
    返回指定 path 的 parent。
    """
    if not path:
        return None
    parent_path = path[:-1]
    return _get_subtree(
        expression,
        parent_path,
    )
def _contains_operator(
    expression: _AMExpr,
    operator: str,
) -> bool:
    """
    判断 expression 是否包含指定 operator。
    """
    return any(
        node.operator == operator
        for node in _collect_nodes(
            expression
        )
        if node.is_operator
    )
# ============================================================
# Random subtree generator
# ============================================================
class _SubtreeGenerator:
    """
    Mutation 内部使用的随机 subtree generator。
    与 V3.9.2 AlphaGenerator 保持相同 Expression API，
    但不直接依赖 AlphaGenerator，避免 mutation / generator
    之间形成循环依赖。
    """
    def __init__(
        self,
        config: AlphaMutationConfig,
        rng: random.Random,
    ) -> None:
        self.config = config
        self.rng = rng
    def generate(
        self,
        max_depth: Optional[int] = None,
    ) -> _AMExpr:
        """
        生成一个合法随机 subtree。
        """
        if max_depth is None:
            max_depth = (
                self.config.subtree_max_depth
            )
        max_depth = max(
            0,
            int(max_depth),
        )
        return self._generate(
            depth=0,
            max_depth=max_depth,
        )
    def _generate(
        self,
        depth: int,
        max_depth: int,
    ) -> _AMExpr:
        """
        递归生成。
        """
        if depth >= max_depth:
            return self._leaf()
        # 防止深度过深时继续生成 binary。
        choices: list[
            tuple[str, float]
        ] = [
            (
                "leaf",
                1.0
                - self.config.subtree_unary_probability
                - self.config.subtree_binary_probability,
            ),
            (
                "unary",
                self.config.subtree_unary_probability,
            ),
            (
                "binary",
                self.config.subtree_binary_probability,
            ),
        ]
        valid_choices = [
            item
            for item in choices
            if item[1] > 0
        ]
        names = [
            item[0]
            for item in valid_choices
        ]
        weights = [
            item[1]
            for item in valid_choices
        ]
        kind = self.rng.choices(
            names,
            weights=weights,
            k=1,
        )[0]
        if kind == "leaf":
            return self._leaf()
        if kind == "unary":
            operator = self.rng.choice(
                self.config.unary_operators
            )
            child = self._generate(
                depth + 1,
                max_depth,
            )
            return _AMExpr.op(
                operator,
                child,
            )
        operator = self.rng.choice(
            self.config.binary_operators
        )
        left = self._generate(
            depth + 1,
            max_depth,
        )
        right = self._generate(
            depth + 1,
            max_depth,
        )
        return _AMExpr.op(
            operator,
            left,
            right,
        )
    def _leaf(
        self,
    ) -> _AMExpr:
        """
        生成 Feature 或 Constant。
        """
        if (
            self.rng.random()
            < self.config.subtree_constant_probability
        ):
            return _AMExpr.constant(
                self.rng.choice(
                    self.config.constants
                )
            )
        return _AMExpr.feature_node(
            self.rng.choice(
                self.config.features
            )
        )
# ============================================================
# Mutation Engine
# ============================================================
class AlphaMutationEngine:
    """
    Alpha Mutation Engine。
    示例：
        config = AlphaMutationConfig(
            max_depth=4,
            max_nodes=15,
            seed=42,
        )
        engine = AlphaMutationEngine(
            config=config
        )
        child = engine.mutate(
            genome
        )
    """
    def __init__(
        self,
        config: Optional[
            AlphaMutationConfig
        ] = None,
        *,
        seed: Optional[int] = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else AlphaMutationConfig()
        )
        actual_seed = (
            self.config.seed
            if seed is None
            else seed
        )
        self.rng = random.Random(
            actual_seed
        )
        self.subtree_generator = (
            _SubtreeGenerator(
                self.config,
                self.rng,
            )
        )
    # ========================================================
    # Public mutation API
    # ========================================================
    def mutate(
        self,
        genome: _AMGenome,
        *,
        mutation_type: Optional[str] = None,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        对 Genome 执行一次 Mutation。
        返回新的 child Genome。
        原始 Genome 不会被修改。
        """
        if not isinstance(
            genome,
            _AMGenome,
        ):
            raise TypeError(
                "genome must be _AMGenome."
            )
        if mutation_type is None:
            mutation_type = (
                self.choose_mutation_type()
            )
        mutation_type = (
            mutation_type.lower().strip()
        )
        method = {
            "feature_mutation":
                self.mutate_feature,
            "constant_mutation":
                self.mutate_constant,
            "operator_mutation":
                self.mutate_operator,
            "subtree_mutation":
                self.mutate_subtree,
            "unary_insert":
                self.insert_unary,
            "unary_delete":
                self.delete_unary,
            "child_replace":
                self.replace_child,
        }.get(
            mutation_type
        )
        if method is None:
            raise InvalidMutationError(
                f"Unsupported mutation type: "
                f"{mutation_type}"
            )
        for _ in range(
            self.config.retry_count
        ):
            try:
                child = method(
                    genome,
                    generation=generation,
                )
                if (
                    child.expression
                    != genome.expression
                ):
                    return child
            except (
                AlphaMutationError,
                ValueError,
                IndexError,
            ):
                continue
        # 如果无法产生有效变异，
        # 返回一个明确记录失败原因的 clone。
        child = genome.clone(
            generation=(
                genome.generation + 1
                if generation is None
                else generation
            ),
            reset_fitness=True,
        )
        child.metadata[
            "mutation_failed"
        ] = True
        child.metadata[
            "mutation_failure_reason"
        ] = (
            "No valid mutation found "
            f"after {self.config.retry_count} "
            "attempts."
        )
        child.mutation_type = (
            mutation_type
        )
        return child
    def mutate_many(
        self,
        genome: _AMGenome,
        n: int,
        *,
        mutation_type: Optional[str] = None,
    ) -> list[_AMGenome]:
        """
        对同一个 parent 产生多个 mutation children。
        """
        if n < 1:
            raise ValueError(
                "n must be >= 1."
            )
        return [
            self.mutate(
                genome,
                mutation_type=mutation_type,
            )
            for _ in range(n)
        ]
    def choose_mutation_type(
        self,
    ) -> str:
        """
        根据配置概率选择 Mutation 类型。
        """
        return _choose_weighted(
            self.rng,
            _weighted_mutation_types(
                self.config
            ),
        )
    # ========================================================
    # Feature mutation
    # ========================================================
    def mutate_feature(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        Feature Mutation。
        例如：
            rank(roe)
        →
            rank(roic)
        """
        expression = genome.expression
        feature_nodes = [
            (
                path,
                node,
            )
            for path, node in zip(
                _collect_paths(expression),
                _collect_nodes(expression),
            )
            if node.is_feature
        ]
        if not feature_nodes:
            raise AlphaMutationError(
                "No feature node available."
            )
        path, node = self.rng.choice(
            feature_nodes
        )
        current = node.feature
        if (
            current is None
        ):
            raise AlphaMutationError(
                "Feature node has no feature."
            )
        if self.config.allow_same_feature:
            feature = self.rng.choice(
                self.config.features
            )
        else:
            feature = _random_different(
                self.rng,
                self.config.features,
                current,
            )
        replacement = (
            _AMExpr.feature_node(
                feature
            )
        )
        new_expression = _replace_subtree(
            expression,
            path,
            replacement,
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "feature_mutation"
            ),
        )
    # ========================================================
    # Constant mutation
    # ========================================================
    def mutate_constant(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        Constant Mutation。
        例如：
            mul(roe, 1)
        →
            mul(roe, 2)
        """
        expression = genome.expression
        constant_nodes = [
            (
                path,
                node,
            )
            for path, node in zip(
                _collect_paths(expression),
                _collect_nodes(expression),
            )
            if node.is_constant
        ]
        if not constant_nodes:
            # 没有 constant 时创建一个
            # binary subtree 并替换随机节点。
            return self._inject_constant(
                genome,
                generation=generation,
            )
        path, node = self.rng.choice(
            constant_nodes
        )
        current = node.value
        value = (
            self.rng.choice(
                self.config.constants
            )
            if self.config.allow_same_constant
            else _random_different(
                self.rng,
                self.config.constants,
                current,
            )
        )
        replacement = (
            _AMExpr.constant(
                float(value)
            )
        )
        new_expression = _replace_subtree(
            expression,
            path,
            replacement,
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "constant_mutation"
            ),
        )
    def _inject_constant(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        当前表达式没有 constant 时，
        尝试通过 binary operator 注入 constant。
        """
        paths = _collect_paths(
            genome.expression
        )
        path = self.rng.choice(
            paths
        )
        target = _get_subtree(
            genome.expression,
            path,
        )
        operator = self.rng.choice(
            self.config.binary_operators
        )
        constant = (
            _AMExpr.constant(
                self.rng.choice(
                    self.config.constants
                )
            )
        )
        new_subtree = (
            _AMExpr.op(
                operator,
                target,
                constant,
            )
        )
        new_expression = _replace_subtree(
            genome.expression,
            path,
            new_subtree,
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "constant_mutation"
            ),
        )
    # ========================================================
    # Operator mutation
    # ========================================================
    def mutate_operator(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        Operator Mutation。
        只替换相同 arity 的 operator。
        例如：
            rank(roe)
        →
            zscore(roe)
        或：
            add(roe, roic)
        →
            mul(roe, roic)
        """
        expression = genome.expression
        operator_nodes = [
            (
                path,
                node,
            )
            for path, node in zip(
                _collect_paths(expression),
                _collect_nodes(expression),
            )
            if node.is_operator
        ]
        if not operator_nodes:
            raise AlphaMutationError(
                "No operator node available."
            )
        path, node = self.rng.choice(
            operator_nodes
        )
        current = node.operator
        if current is None:
            raise AlphaMutationError(
                "Operator node has no operator."
            )
        arity = get_operator_arity(
            current
        )
        if arity == 1:
            candidates = [
                operator
                for operator in (
                    self.config.unary_operators
                )
                if (
                    get_operator_arity(
                        operator
                    )
                    == 1
                )
            ]
        elif arity == 2:
            candidates = [
                operator
                for operator in (
                    self.config.binary_operators
                )
                if (
                    get_operator_arity(
                        operator
                    )
                    == 2
                )
            ]
        else:
            raise AlphaMutationError(
                f"Unsupported operator arity: "
                f"{arity}"
            )
        if not self.config.allow_same_operator:
            candidates = [
                operator
                for operator in candidates
                if operator != current
            ]
        if not candidates:
            raise AlphaMutationError(
                "No alternative operator "
                "available."
            )
        replacement_operator = (
            self.rng.choice(
                candidates
            )
        )
        new_expression = (
            _AMExpr.op(
                replacement_operator,
                *node.children,
            )
        )
        new_expression = _replace_subtree(
            expression,
            path,
            new_expression,
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "operator_mutation"
            ),
        )
    # ========================================================
    # Subtree mutation
    # ========================================================
    def mutate_subtree(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        Subtree Mutation。
        随机选择一个 subtree，
        使用新的随机 subtree 替换。
        这是 Evolution Engine 最重要的 Mutation 之一。
        """
        expression = genome.expression
        paths = _collect_paths(
            expression
        )
        path = self.rng.choice(
            paths
        )
        old_subtree = _get_subtree(
            expression,
            path,
        )
        remaining_depth = max(
            0,
            self.config.max_depth
            - self._path_depth(path),
        )
        subtree_depth = min(
            self.config.subtree_max_depth,
            remaining_depth,
        )
        new_subtree = (
            self.subtree_generator.generate(
                max_depth=subtree_depth
            )
        )
        if (
            new_subtree
            == old_subtree
        ):
            raise AlphaMutationError(
                "Generated subtree is identical."
            )
        new_expression = _replace_subtree(
            expression,
            path,
            new_subtree,
        )
        self._validate_expression(
            new_expression
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "subtree_mutation"
            ),
        )
    # ========================================================
    # Unary insertion
    # ========================================================
    def insert_unary(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        Unary Insert。
        例如：
            roe
        →
            rank(roe)
        或：
            add(roe, roic)
        →
            zscore(add(roe, roic))
        """
        expression = genome.expression
        paths = _collect_paths(
            expression
        )
        path = self.rng.choice(
            paths
        )
        target = _get_subtree(
            expression,
            path,
        )
        if (
            target.depth()
            + 1
            > self.config.max_depth
        ):
            raise MutationConstraintError(
                "Unary insertion would exceed "
                "max_depth."
            )
        operator = self.rng.choice(
            self.config.unary_operators
        )
        new_subtree = (
            _AMExpr.op(
                operator,
                target,
            )
        )
        new_expression = _replace_subtree(
            expression,
            path,
            new_subtree,
        )
        self._validate_expression(
            new_expression
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "unary_insert"
            ),
        )
    # ========================================================
    # Unary deletion
    # ========================================================
    def delete_unary(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        Unary Delete。
        例如：
            rank(roe)
        →
            roe
        """
        expression = genome.expression
        unary_nodes = [
            (
                path,
                node,
            )
            for path, node in zip(
                _collect_paths(expression),
                _collect_nodes(expression),
            )
            if (
                node.is_operator
                and node.operator is not None
                and is_unary_operator(
                    node.operator
                )
            )
        ]
        if not unary_nodes:
            raise AlphaMutationError(
                "No unary operator available."
            )
        path, node = self.rng.choice(
            unary_nodes
        )
        if len(node.children) != 1:
            raise AlphaMutationError(
                "Unary operator must have "
                "exactly one child."
            )
        replacement = node.children[0]
        new_expression = _replace_subtree(
            expression,
            path,
            replacement,
        )
        self._validate_expression(
            new_expression
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "unary_delete"
            ),
        )
    # ========================================================
    # Child replacement
    # ========================================================
    def replace_child(
        self,
        genome: _AMGenome,
        *,
        generation: Optional[int] = None,
    ) -> _AMGenome:
        """
        Child Replace。
        选择一个 operator，
        随机替换其中一个 child。
        例如：
            add(roe, momentum_20)
        →
            add(roic, momentum_20)
        """
        expression = genome.expression
        operator_nodes = [
            (
                path,
                node,
            )
            for path, node in zip(
                _collect_paths(expression),
                _collect_nodes(expression),
            )
            if (
                node.is_operator
                and len(node.children) > 0
            )
        ]
        if not operator_nodes:
            raise AlphaMutationError(
                "No operator with children."
            )
        path, node = self.rng.choice(
            operator_nodes
        )
        child_index = self.rng.randrange(
            len(node.children)
        )
        child_path = (
            path
            + (child_index,)
        )
        current_child = (
            node.children[child_index]
        )
        remaining_depth = max(
            0,
            self.config.max_depth
            - self._path_depth(
                child_path
            ),
        )
        replacement = (
            self.subtree_generator.generate(
                max_depth=min(
                    self.config.subtree_max_depth,
                    remaining_depth,
                )
            )
        )
        if (
            replacement
            == current_child
        ):
            raise AlphaMutationError(
                "Replacement child is identical."
            )
        new_expression = _replace_subtree(
            expression,
            child_path,
            replacement,
        )
        self._validate_expression(
            new_expression
        )
        return self._create_child(
            genome,
            new_expression,
            generation=generation,
            mutation_type=(
                "child_replace"
            ),
        )
    # ========================================================
    # Validation
    # ========================================================
    def _validate_expression(
        self,
        expression: _AMExpr,
    ) -> None:
        """
        验证 Mutation 后表达式。
        """
        try:
            expression.validate(
                max_depth=self.config.max_depth,
                max_nodes=self.config.max_nodes,
            )
        except Exception as exc:
            raise MutationConstraintError(
                "Mutated expression violates "
                "expression constraints."
            ) from exc
        if (
            expression.depth()
            > self.config.max_depth
        ):
            raise MutationConstraintError(
                "Expression depth exceeds "
                "max_depth."
            )
        if (
            expression.node_count()
            > self.config.max_nodes
        ):
            raise MutationConstraintError(
                "Expression node count exceeds "
                "max_nodes."
            )
    # ========================================================
    # Child construction
    # ========================================================
    def _create_child(
        self,
        genome: _AMGenome,
        expression: _AMExpr,
        *,
        generation: Optional[int],
        mutation_type: str,
    ) -> _AMGenome:
        """
        创建 Mutation Child。
        """
        self._validate_expression(
            expression
        )
        child = genome.create_child(
            expression=expression,
            generation=(
                genome.generation + 1
                if generation is None
                else generation
            ),
            mutation_type=mutation_type,
            metadata={
                "mutation_engine_version": (
                    "3.9.3"
                ),
                "parent_expression": (
                    genome.expression_string
                ),
            },
        )
        # 新表达式必须重新 evaluation。
        child.reset_evaluation()
        return child
    @staticmethod
    def _path_depth(
        path: tuple[int, ...],
    ) -> int:
        """
        计算 path 深度。
        """
        return len(path)
# ============================================================
# Functional API
# ============================================================
def mutate_genome(
    genome: _AMGenome,
    *,
    config: Optional[
        AlphaMutationConfig
    ] = None,
    mutation_type: Optional[str] = None,
    seed: Optional[int] = None,
) -> _AMGenome:
    """
    Functional Mutation API。
    """
    engine = AlphaMutationEngine(
        config=config,
        seed=seed,
    )
    return engine.mutate(
        genome,
        mutation_type=mutation_type,
    )
def mutate_expression(
    expression: _AMExpr,
    *,
    config: Optional[
        AlphaMutationConfig
    ] = None,
    mutation_type: Optional[str] = None,
    seed: Optional[int] = None,
) -> _AMExpr:
    """
    直接 Mutation _AMExpr。
    返回新的 _AMExpr。
    """
    genome = _AMGenome(
        expression=expression
    )
    child = mutate_genome(
        genome,
        config=config,
        mutation_type=mutation_type,
        seed=seed,
    )
    return child.expression
# ============================================================
# Public exports
# ============================================================
__all__ = [
    "DEFAULT_FEATURES",
    "DEFAULT_UNARY_OPERATORS",
    "DEFAULT_BINARY_OPERATORS",
    "DEFAULT_CONSTANTS",
    "DEFAULT_MUTATION_TYPES",
    "AlphaMutationError",
    "InvalidMutationError",
    "MutationConstraintError",
    "AlphaMutationConfig",
    "AlphaMutationEngine",
    "mutate_genome",
    "mutate_expression",
]
