from __future__ import annotations

import copy
import random


class AlphaCrossover:
    def crossover(self, parent_a, parent_b):
        child = copy.deepcopy(parent_a)
        if not child.children or not parent_b.children:
            return child
        index = random.randrange(len(child.children))
        source = random.choice(parent_b.children)
        child.children[index] = copy.deepcopy(source)
        return child

# ============================================================
# V3.9.3 Alpha Crossover Engine (appended)
# 旧版 AlphaCrossover（legacy）保留；以下为 V3.9.3 新引擎。
# expression 使用项目的 V3.9.2 实现 AlphaExpressionV392，
# genome 使用 V3.9.3 的 AlphaGenomeV393。为避免覆盖旧版
# 模块全局名，使用私有别名 _CXExpr / _CXGenome。
# ============================================================

from dataclasses import dataclass
from typing import Any, Optional, Sequence
import random
from alpha.expression import (
    AlphaExpressionV392 as _CXExpr,
)
from evolution.alpha_genome import (
    AlphaGenomeV393 as _CXGenome,
)
# ============================================================
# Constants
# ============================================================
DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_NODES = 15
DEFAULT_RETRY_COUNT = 12
DEFAULT_CROSSOVER_TYPES = (
    "subtree",
    "root",
)
# ============================================================
# Exceptions
# ============================================================
class AlphaCrossoverError(Exception):
    """Alpha Crossover 基础异常。"""
class CrossoverConstraintError(
    AlphaCrossoverError
):
    """交叉后表达式违反约束。"""
class InvalidCrossoverError(
    AlphaCrossoverError
):
    """Crossover 参数非法。"""
# ============================================================
# Configuration
# ============================================================
@dataclass(frozen=True)
class AlphaCrossoverConfig:
    """
    Alpha Crossover 配置。
    """
    max_depth: int = DEFAULT_MAX_DEPTH
    max_nodes: int = DEFAULT_MAX_NODES
    retry_count: int = DEFAULT_RETRY_COUNT
    subtree_probability: float = 0.90
    root_probability: float = 0.10
    allow_root_crossover: bool = True
    allow_same_expression: bool = False
    seed: Optional[int] = 42
    def __post_init__(self) -> None:
        if self.max_depth < 1:
            raise ValueError(
                "max_depth must be >= 1."
            )
        if self.max_nodes < 1:
            raise ValueError(
                "max_nodes must be >= 1."
            )
        if self.retry_count < 1:
            raise ValueError(
                "retry_count must be >= 1."
            )
        if not (
            0.0
            <= self.subtree_probability
            <= 1.0
        ):
            raise ValueError(
                "subtree_probability must "
                "be between 0 and 1."
            )
        if not (
            0.0
            <= self.root_probability
            <= 1.0
        ):
            raise ValueError(
                "root_probability must "
                "be between 0 and 1."
            )
        if (
            self.subtree_probability
            + self.root_probability
            <= 0
        ):
            raise ValueError(
                "At least one crossover "
                "probability must be positive."
            )
# ============================================================
# Expression tree utilities
# ============================================================
def _collect_paths(
    expression: _CXExpr,
) -> list[tuple[int, ...]]:
    """
    收集 Expression Tree 所有节点 path。
    Root:
        ()
    第一层：
        (0,)
        (1,)
    第二层：
        (0,0)
        (0,1)
        ...
    """
    paths: list[
        tuple[int, ...]
    ] = []
    def visit(
        node: _CXExpr,
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
    expression: _CXExpr,
    path: tuple[int, ...],
) -> _CXExpr:
    """
    根据 path 获取 subtree。
    """
    node = expression
    for index in path:
        if (
            index < 0
            or index >= len(
                node.children
            )
        ):
            raise IndexError(
                "Invalid expression path."
            )
        node = node.children[index]
    return node
def _replace_subtree(
    expression: _CXExpr,
    path: tuple[int, ...],
    replacement: _CXExpr,
) -> _CXExpr:
    """
    替换 subtree。
    不修改原始 expression。
    """
    if not path:
        return replacement
    index = path[0]
    if (
        not expression.is_operator
        or index >= len(
            expression.children
        )
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
    return _CXExpr.op(
        expression.operator,
        *children,
    )
def _path_depth(
    path: tuple[int, ...],
) -> int:
    """
    Path depth。
    """
    return len(path)
def _subtree_height(
    expression: _CXExpr,
) -> int:
    """
    返回 subtree depth。
    """
    return expression.depth()
def _same_expression(
    left: _CXExpr,
    right: _CXExpr,
) -> bool:
    """
    判断两个 AlphaExpression 是否等价。
    canonical() 可以处理 add / mul
    等交换律 operator。
    """
    return (
        left.canonical()
        == right.canonical()
    )
# ============================================================
# Compatibility
# ============================================================
def _is_compatible_subtree(
    target_expression: _CXExpr,
    target_path: tuple[int, ...],
    donor_subtree: _CXExpr,
    *,
    max_depth: int,
) -> bool:
    """
    判断 donor subtree 放入 target path 后，
    是否可能超过 max_depth。
    这里不改变 expression。
    """
    target_depth = _path_depth(
        target_path
    )
    resulting_depth = (
        target_depth
        + donor_subtree.depth()
    )
    return (
        resulting_depth
        <= max_depth
    )
# ============================================================
# Crossover Engine
# ============================================================
class AlphaCrossoverEngine:
    """
    Alpha Crossover Engine。
    示例：
        engine = AlphaCrossoverEngine()
        child_a, child_b = engine.crossover(
            parent_a,
            parent_b,
        )
    """
    def __init__(
        self,
        config: Optional[
            AlphaCrossoverConfig
        ] = None,
        *,
        seed: Optional[int] = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else AlphaCrossoverConfig()
        )
        actual_seed = (
            self.config.seed
            if seed is None
            else seed
        )
        self.rng = random.Random(
            actual_seed
        )
    # ========================================================
    # Public API
    # ========================================================
    def crossover(
        self,
        parent_a: _CXGenome,
        parent_b: _CXGenome,
        *,
        crossover_type: Optional[str] = None,
        generation: Optional[int] = None,
    ) -> tuple[
        _CXGenome,
        _CXGenome,
    ]:
        """
        对两个 parent 执行 Crossover。
        返回两个 child。
        Child A:
            Parent A 的主体
            +
            Parent B 的 subtree
        Child B:
            Parent B 的主体
            +
            Parent A 的 subtree
        """
        self._validate_parents(
            parent_a,
            parent_b,
        )
        if crossover_type is None:
            crossover_type = (
                self.choose_crossover_type()
            )
        crossover_type = (
            crossover_type
            .lower()
            .strip()
        )
        if (
            crossover_type
            == "subtree"
        ):
            return self.subtree_crossover(
                parent_a,
                parent_b,
                generation=generation,
            )
        if (
            crossover_type
            == "root"
        ):
            return self.root_crossover(
                parent_a,
                parent_b,
                generation=generation,
            )
        raise InvalidCrossoverError(
            f"Unsupported crossover type: "
            f"{crossover_type}"
        )
    def crossover_many(
        self,
        parent_a: _CXGenome,
        parent_b: _CXGenome,
        n: int,
        *,
        crossover_type: Optional[str] = None,
    ) -> list[_CXGenome]:
        """
        产生多个 child。
        每次 crossover 返回两个 child，
        最终截取前 n 个。
        """
        if n < 1:
            raise ValueError(
                "n must be >= 1."
            )
        children: list[
            _CXGenome
        ] = []
        while len(children) < n:
            child_a, child_b = (
                self.crossover(
                    parent_a,
                    parent_b,
                    crossover_type=(
                        crossover_type
                    ),
                )
            )
            children.append(
                child_a
            )
            if len(children) < n:
                children.append(
                    child_b
                )
        return children[:n]
    def choose_crossover_type(
        self,
    ) -> str:
        """
        按配置概率选择 crossover 类型。
        """
        options: list[
            tuple[str, float]
        ] = []
        if (
            self.config.subtree_probability
            > 0
        ):
            options.append(
                (
                    "subtree",
                    self.config.subtree_probability,
                )
            )
        if (
            self.config.allow_root_crossover
            and self.config.root_probability
            > 0
        ):
            options.append(
                (
                    "root",
                    self.config.root_probability,
                )
            )
        if not options:
            raise InvalidCrossoverError(
                "No crossover type available."
            )
        return self.rng.choices(
            [item[0] for item in options],
            weights=[
                item[1]
                for item in options
            ],
            k=1,
        )[0]
    # ========================================================
    # Subtree crossover
    # ========================================================
    def subtree_crossover(
        self,
        parent_a: _CXGenome,
        parent_b: _CXGenome,
        *,
        generation: Optional[int] = None,
    ) -> tuple[
        _CXGenome,
        _CXGenome,
    ]:
        """
        Subtree Crossover。
        这是主要的遗传进化方式。
        例如：
        Parent A:
            add(
                rank(roe),
                momentum_20
            )
        Parent B:
            mul(
                zscore(roic),
                pb_inverse
            )
        可能产生：
        Child A:
            add(
                zscore(roic),
                momentum_20
            )
        Child B:
            mul(
                rank(roe),
                pb_inverse
            )
        """
        expression_a = (
            parent_a.expression
        )
        expression_b = (
            parent_b.expression
        )
        paths_a = _collect_paths(
            expression_a
        )
        paths_b = _collect_paths(
            expression_b
        )
        for _ in range(
            self.config.retry_count
        ):
            path_a = self.rng.choice(
                paths_a
            )
            path_b = self.rng.choice(
                paths_b
            )
            subtree_a = _get_subtree(
                expression_a,
                path_a,
            )
            subtree_b = _get_subtree(
                expression_b,
                path_b,
            )
            # ------------------------------------------------
            # 如果完全相同，尝试其他组合
            # ------------------------------------------------
            if (
                not self.config.allow_same_expression
                and _same_expression(
                    subtree_a,
                    subtree_b,
                )
            ):
                continue
            # ------------------------------------------------
            # Depth constraint
            # ------------------------------------------------
            if not _is_compatible_subtree(
                expression_a,
                path_a,
                subtree_b,
                max_depth=(
                    self.config.max_depth
                ),
            ):
                continue
            if not _is_compatible_subtree(
                expression_b,
                path_b,
                subtree_a,
                max_depth=(
                    self.config.max_depth
                ),
            ):
                continue
            # ------------------------------------------------
            # Construct children
            # ------------------------------------------------
            child_expression_a = (
                _replace_subtree(
                    expression_a,
                    path_a,
                    subtree_b,
                )
            )
            child_expression_b = (
                _replace_subtree(
                    expression_b,
                    path_b,
                    subtree_a,
                )
            )
            # ------------------------------------------------
            # Validate
            # ------------------------------------------------
            if not self._is_valid_expression(
                child_expression_a
            ):
                continue
            if not self._is_valid_expression(
                child_expression_b
            ):
                continue
            # ------------------------------------------------
            # Avoid identical parent
            # ------------------------------------------------
            if (
                not self.config.allow_same_expression
                and (
                    _same_expression(
                        child_expression_a,
                        expression_a,
                    )
                    or _same_expression(
                        child_expression_b,
                        expression_b,
                    )
                )
            ):
                continue
            child_a = self._create_child(
                parent_a,
                parent_b,
                child_expression_a,
                generation=generation,
            )
            child_b = self._create_child(
                parent_b,
                parent_a,
                child_expression_b,
                generation=generation,
            )
            return child_a, child_b
        # ----------------------------------------------------
        # Crossover failed
        # ----------------------------------------------------
        return self._fallback_children(
            parent_a,
            parent_b,
            generation=generation,
        )
    # ========================================================
    # Root crossover
    # ========================================================
    def root_crossover(
        self,
        parent_a: _CXGenome,
        parent_b: _CXGenome,
        *,
        generation: Optional[int] = None,
    ) -> tuple[
        _CXGenome,
        _CXGenome,
    ]:
        """
        Root Crossover。
        直接交换两个完整 AlphaExpression。
        例如：
            Parent A = rank(roe)
            Parent B = zscore(roic)
        →
            Child A = zscore(roic)
            Child B = rank(roe)
        注意：
            这种方式容易产生 duplicate，
            所以默认概率较低。
        """
        expression_a = (
            parent_a.expression
        )
        expression_b = (
            parent_b.expression
        )
        if (
            not self.config.allow_same_expression
            and _same_expression(
                expression_a,
                expression_b,
            )
        ):
            return self._fallback_children(
                parent_a,
                parent_b,
                generation=generation,
            )
        if not self._is_valid_expression(
            expression_a
        ):
            raise CrossoverConstraintError(
                "Parent A expression is invalid."
            )
        if not self._is_valid_expression(
            expression_b
        ):
            raise CrossoverConstraintError(
                "Parent B expression is invalid."
            )
        child_a = self._create_child(
            parent_a,
            parent_b,
            expression_b,
            generation=generation,
            crossover_type="root_crossover",
        )
        child_b = self._create_child(
            parent_b,
            parent_a,
            expression_a,
            generation=generation,
            crossover_type="root_crossover",
        )
        return child_a, child_b
    # ========================================================
    # Validation
    # ========================================================
    def _validate_parents(
        self,
        parent_a: _CXGenome,
        parent_b: _CXGenome,
    ) -> None:
        """
        验证 parents。
        """
        if not isinstance(
            parent_a,
            _CXGenome,
        ):
            raise TypeError(
                "parent_a must be AlphaGenome."
            )
        if not isinstance(
            parent_b,
            _CXGenome,
        ):
            raise TypeError(
                "parent_b must be AlphaGenome."
            )
        if not self._is_valid_expression(
            parent_a.expression
        ):
            raise CrossoverConstraintError(
                "Parent A expression violates "
                "evolution constraints."
            )
        if not self._is_valid_expression(
            parent_b.expression
        ):
            raise CrossoverConstraintError(
                "Parent B expression violates "
                "evolution constraints."
            )
    def _is_valid_expression(
        self,
        expression: _CXExpr,
    ) -> bool:
        """
        判断 expression 是否符合限制。
        """
        try:
            expression.validate(
                max_depth=(
                    self.config.max_depth
                ),
                max_nodes=(
                    self.config.max_nodes
                ),
            )
        except Exception:
            return False
        if (
            expression.depth()
            > self.config.max_depth
        ):
            return False
        if (
            expression.node_count()
            > self.config.max_nodes
        ):
            return False
        return True
    # ========================================================
    # Child creation
    # ========================================================
    def _create_child(
        self,
        base_parent: _CXGenome,
        second_parent: _CXGenome,
        expression: _CXExpr,
        *,
        generation: Optional[int],
        crossover_type: str = (
            "subtree_crossover"
        ),
    ) -> _CXGenome:
        """
        创建 crossover child。
        """
        if not self._is_valid_expression(
            expression
        ):
            raise CrossoverConstraintError(
                "Child expression violates "
                "evolution constraints."
            )
        child = base_parent.create_child(
            expression=expression,
            generation=(
                base_parent.generation + 1
                if generation is None
                else generation
            ),
            crossover_type=(
                crossover_type
            ),
            parents=(
                base_parent,
                second_parent,
            ),
            metadata={
                "crossover_engine_version": (
                    "3.9.3"
                ),
                "parent_a_expression": (
                    base_parent.expression_string
                ),
                "parent_b_expression": (
                    second_parent.expression_string
                ),
            },
        )
        child.reset_evaluation()
        return child
    # ========================================================
    # Fallback
    # ========================================================
    def _fallback_children(
        self,
        parent_a: _CXGenome,
        parent_b: _CXGenome,
        *,
        generation: Optional[int],
    ) -> tuple[
        _CXGenome,
        _CXGenome,
    ]:
        """
        Crossover 无法产生新表达式时的 fallback。
        注意：
            不会伪造 fitness。
        返回 clone，并明确标记 crossover failed。
        """
        child_a = parent_a.clone(
            generation=(
                parent_a.generation + 1
                if generation is None
                else generation
            ),
            reset_fitness=True,
            metadata_update={
                "crossover_failed": True,
                "crossover_failure_reason": (
                    "No valid crossover found."
                ),
            },
        )
        child_b = parent_b.clone(
            generation=(
                parent_b.generation + 1
                if generation is None
                else generation
            ),
            reset_fitness=True,
            metadata_update={
                "crossover_failed": True,
                "crossover_failure_reason": (
                    "No valid crossover found."
                ),
            },
        )
        child_a.crossover_type = (
            "subtree_crossover_failed"
        )
        child_b.crossover_type = (
            "subtree_crossover_failed"
        )
        return child_a, child_b
# ============================================================
# Functional API
# ============================================================
def crossover_genomes(
    parent_a: _CXGenome,
    parent_b: _CXGenome,
    *,
    config: Optional[
        AlphaCrossoverConfig
    ] = None,
    crossover_type: Optional[str] = None,
    seed: Optional[int] = None,
) -> tuple[
    _CXGenome,
    _CXGenome,
]:
    """
    Functional Crossover API。
    """
    engine = AlphaCrossoverEngine(
        config=config,
        seed=seed,
    )
    return engine.crossover(
        parent_a,
        parent_b,
        crossover_type=crossover_type,
    )
def crossover_expressions(
    expression_a: _CXExpr,
    expression_b: _CXExpr,
    *,
    config: Optional[
        AlphaCrossoverConfig
    ] = None,
    crossover_type: Optional[str] = None,
    seed: Optional[int] = None,
) -> tuple[
    _CXExpr,
    _CXExpr,
]:
    """
    直接对两个 AlphaExpression 执行 Crossover。
    返回两个新的 AlphaExpression。
    """
    parent_a = _CXGenome(
        expression=expression_a
    )
    parent_b = _CXGenome(
        expression=expression_b
    )
    child_a, child_b = (
        crossover_genomes(
            parent_a,
            parent_b,
            config=config,
            crossover_type=crossover_type,
            seed=seed,
        )
    )
    return (
        child_a.expression,
        child_b.expression,
    )
# ============================================================
# Public exports
# ============================================================
__all__ = [
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_NODES",
    "DEFAULT_RETRY_COUNT",
    "DEFAULT_CROSSOVER_TYPES",
    "AlphaCrossoverError",
    "CrossoverConstraintError",
    "InvalidCrossoverError",
    "AlphaCrossoverConfig",
    "AlphaCrossoverEngine",
    "crossover_genomes",
    "crossover_expressions",
]
