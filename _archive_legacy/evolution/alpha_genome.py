from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlphaGenome:
    formula: str
    score: float = 0.0
    ic: float = 0.0
    icir: float = 0.0
    oos_score: float = 0.0
    complexity: int = 0
    generation: int = 0
    status: str = "EXPERIMENT"

    def fitness(self):
        return (
            self.oos_score * 0.5
            + self.ic * 0.2
            + self.icir * 0.2
            - self.complexity * 0.01
        )

# ============================================================
# V3.9.3 Alpha Genome (appended, V393 suffix)
# 与 legacy AlphaGenome（formula 版）语义不同，为避免破坏
# tests/test_v39.py 等已有引用，V3.9.3 主类命名为 AlphaGenomeV393。
# expression 使用项目的 V3.9.2 实现 AlphaExpressionV392
# （具备 feature_node/canonical/to_dict/from_dict/node_count/depth/
#  feature_names/to_string 完整接口）。
# ============================================================

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from uuid import uuid4

from alpha.expression import AlphaExpressionV392 as AlphaExpression
# ============================================================
# Constants
# ============================================================
GENOME_VERSION = "3.9.3"
DEFAULT_FITNESS = float("-inf")
DEFAULT_GENERATION = 0
# ============================================================
# Helper functions
# ============================================================
def _utc_now_iso() -> str:
    """
    返回 UTC ISO-8601 时间。
    """
    return (
        datetime.now(timezone.utc)
        .isoformat()
    )
def _safe_float(
    value: Any,
    default: float = float("nan"),
) -> float:
    """
    安全转换 float。
    """
    if value is None:
        return default
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default
def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    安全转换 int。
    """
    if value is None:
        return default
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default
def _clean_metadata(
    metadata: Optional[
        Mapping[str, Any]
    ],
) -> dict[str, Any]:
    """
    将 metadata 转换成普通 dict。
    避免外部 Mapping 被后续修改影响 Genome。
    """
    if metadata is None:
        return {}
    return dict(metadata)
# ============================================================
# AlphaGenomeV393
# ============================================================
@dataclass
class AlphaGenomeV393:
    """
    Alpha Evolution Genome（V3.9.3）。
    一个 Genome = 一个 AlphaExpression + 它当前的评价状态。
    示例：
        expression =
            rank(roe)
        genome =
            AlphaGenomeV393(
                expression=expression
            )
    在 fitness evaluation 后：
        genome.fitness = 1.37
        genome.ic = 0.052
        genome.icir = 1.84
        genome.quantile_spread = 0.031
        genome.turnover = 0.42
    之后进入：
        selection
        crossover
        mutation
    """
    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------
    genome_id: str = field(
        default_factory=lambda: uuid4().hex
    )
    expression: AlphaExpression = field(
        default_factory=lambda:
            AlphaExpression.feature_node(
                "roe"
            )
    )
    # --------------------------------------------------------
    # Evolution state
    # --------------------------------------------------------
    generation: int = DEFAULT_GENERATION
    fitness: float = DEFAULT_FITNESS
    rank: Optional[int] = None
    selected: bool = False
    elite: bool = False
    # --------------------------------------------------------
    # Core Alpha metrics
    # --------------------------------------------------------
    ic: float = float("nan")
    icir: float = float("nan")
    quantile_spread: float = float("nan")
    long_short_spread: float = float("nan")
    hit_rate: float = float("nan")
    # --------------------------------------------------------
    # Risk / trading characteristics
    # --------------------------------------------------------
    turnover: float = float("nan")
    volatility: float = float("nan")
    sharpe: float = float("nan")
    max_drawdown: float = float("nan")
    # --------------------------------------------------------
    # Complexity
    # --------------------------------------------------------
    complexity: float = float("nan")
    node_count: int = 0
    depth: int = 0
    # --------------------------------------------------------
    # Correlation
    # --------------------------------------------------------
    max_correlation: float = float("nan")
    mean_correlation: float = float("nan")
    correlation_penalty: float = 0.0
    # --------------------------------------------------------
    # OOS
    # --------------------------------------------------------
    oos_ic: float = float("nan")
    oos_icir: float = float("nan")
    oos_quantile_spread: float = float("nan")
    oos_turnover: float = float("nan")
    oos_passed: bool = False
    # --------------------------------------------------------
    # Lineage
    # --------------------------------------------------------
    parent_ids: tuple[str, ...] = field(
        default_factory=tuple
    )
    parent_expression_hashes: tuple[
        str, ...
    ] = field(
        default_factory=tuple
    )
    mutation_type: Optional[str] = None
    crossover_type: Optional[str] = None
    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    created_at: str = field(
        default_factory=_utc_now_iso
    )
    updated_at: str = field(
        default_factory=_utc_now_iso
    )
    genome_version: str = GENOME_VERSION
    # ========================================================
    # Initialization
    # ========================================================
    def __post_init__(self) -> None:
        """
        初始化后进行规范化。
        """
        if not isinstance(
            self.expression,
            AlphaExpression,
        ):
            raise TypeError(
                "expression must be "
                "AlphaExpression."
            )
        if not self.genome_id:
            self.genome_id = uuid4().hex
        self.generation = _safe_int(
            self.generation,
            DEFAULT_GENERATION,
        )
        if self.generation < 0:
            raise ValueError(
                "generation cannot be negative."
            )
        self.fitness = _safe_float(
            self.fitness,
            DEFAULT_FITNESS,
        )
        self.ic = _safe_float(
            self.ic
        )
        self.icir = _safe_float(
            self.icir
        )
        self.quantile_spread = _safe_float(
            self.quantile_spread
        )
        self.long_short_spread = _safe_float(
            self.long_short_spread
        )
        self.hit_rate = _safe_float(
            self.hit_rate
        )
        self.turnover = _safe_float(
            self.turnover
        )
        self.volatility = _safe_float(
            self.volatility
        )
        self.sharpe = _safe_float(
            self.sharpe
        )
        self.max_drawdown = _safe_float(
            self.max_drawdown
        )
        self.complexity = _safe_float(
            self.complexity
        )
        if self.node_count <= 0:
            self.node_count = (
                self.expression.node_count()
            )
        if self.depth <= 0:
            self.depth = (
                self.expression.depth()
            )
        self.max_correlation = _safe_float(
            self.max_correlation
        )
        self.mean_correlation = _safe_float(
            self.mean_correlation
        )
        self.correlation_penalty = _safe_float(
            self.correlation_penalty,
            0.0,
        )
        self.oos_ic = _safe_float(
            self.oos_ic
        )
        self.oos_icir = _safe_float(
            self.oos_icir
        )
        self.oos_quantile_spread = _safe_float(
            self.oos_quantile_spread
        )
        self.oos_turnover = _safe_float(
            self.oos_turnover
        )
        self.parent_ids = tuple(
            self.parent_ids
        )
        self.parent_expression_hashes = tuple(
            self.parent_expression_hashes
        )
        self.metadata = _clean_metadata(
            self.metadata
        )
        if not self.created_at:
            self.created_at = _utc_now_iso()
        self.updated_at = _utc_now_iso()
    # ========================================================
    # Expression information
    # ========================================================
    @property
    def expression_string(self) -> str:
        """
        返回 Alpha 表达式字符串。
        例如：
            rank(roe)
        """
        return self.expression.to_string()
    @property
    def canonical_expression(self) -> str:
        """
        返回用于去重的 canonical expression。
        """
        return self.expression.canonical()
    @property
    def expression_hash(self) -> str:
        """
        返回稳定的表达式 hash。
        Python 内置 hash() 不保证跨进程稳定，
        因此这里使用 SHA-256。
        """
        import hashlib
        return hashlib.sha256(
            self.canonical_expression.encode(
                "utf-8"
            )
        ).hexdigest()
    @property
    def feature_names(self) -> tuple[str, ...]:
        """
        Alpha 所使用的 feature。
        """
        return self.expression.feature_names()
    # ========================================================
    # Fitness state
    # ========================================================
    @property
    def is_evaluated(self) -> bool:
        """
        判断 Genome 是否已经计算过 fitness。
        """
        return self.fitness != DEFAULT_FITNESS
    @property
    def has_finite_fitness(self) -> bool:
        """
        判断 fitness 是否为有效有限数字。
        """
        import math
        return math.isfinite(
            self.fitness
        )
    @property
    def is_valid_oos(self) -> bool:
        """
        是否通过 OOS 验证。
        """
        return bool(
            self.oos_passed
        )
    # ========================================================
    # Fitness update
    # ========================================================
    def update_fitness(
        self,
        fitness: float,
        *,
        ic: Optional[float] = None,
        icir: Optional[float] = None,
        quantile_spread: Optional[float] = None,
        turnover: Optional[float] = None,
        complexity: Optional[float] = None,
        correlation_penalty: Optional[float] = None,
        **metrics: Any,
    ) -> None:
        """
        更新 Genome 的 fitness 和相关指标。
        例如：
            genome.update_fitness(
                fitness=1.25,
                ic=0.045,
                icir=1.72,
                quantile_spread=0.032,
            )
        """
        self.fitness = _safe_float(
            fitness
        )
        if ic is not None:
            self.ic = _safe_float(
                ic
            )
        if icir is not None:
            self.icir = _safe_float(
                icir
            )
        if quantile_spread is not None:
            self.quantile_spread = (
                _safe_float(
                    quantile_spread
                )
            )
        if turnover is not None:
            self.turnover = _safe_float(
                turnover
            )
        if complexity is not None:
            self.complexity = _safe_float(
                complexity
            )
        if (
            correlation_penalty
            is not None
        ):
            self.correlation_penalty = (
                _safe_float(
                    correlation_penalty,
                    0.0,
                )
            )
        # 将额外 metrics 保存到 metadata。
        if metrics:
            self.metadata.update(
                metrics
            )
        self.updated_at = _utc_now_iso()
    # ========================================================
    # OOS update
    # ========================================================
    def update_oos(
        self,
        *,
        oos_ic: Optional[float] = None,
        oos_icir: Optional[float] = None,
        oos_quantile_spread: Optional[
            float
        ] = None,
        oos_turnover: Optional[
            float
        ] = None,
        passed: Optional[bool] = None,
        **metrics: Any,
    ) -> None:
        """
        更新 OOS 验证结果。
        """
        if oos_ic is not None:
            self.oos_ic = _safe_float(
                oos_ic
            )
        if oos_icir is not None:
            self.oos_icir = _safe_float(
                oos_icir
            )
        if (
            oos_quantile_spread
            is not None
        ):
            self.oos_quantile_spread = (
                _safe_float(
                    oos_quantile_spread
                )
            )
        if oos_turnover is not None:
            self.oos_turnover = _safe_float(
                oos_turnover
            )
        if passed is not None:
            self.oos_passed = bool(
                passed
            )
        if metrics:
            self.metadata.update(
                metrics
            )
        self.updated_at = _utc_now_iso()
    # ========================================================
    # Evolution state
    # ========================================================
    def mark_selected(
        self,
        selected: bool = True,
    ) -> None:
        """
        标记是否进入下一代。
        """
        self.selected = bool(
            selected
        )
        self.updated_at = _utc_now_iso()
    def mark_elite(
        self,
        elite: bool = True,
    ) -> None:
        """
        标记是否为 elite。
        """
        self.elite = bool(
            elite
        )
        self.updated_at = _utc_now_iso()
    def set_rank(
        self,
        rank: Optional[int],
    ) -> None:
        """
        设置种群排名。
        """
        if rank is not None:
            rank = int(rank)
            if rank < 1:
                raise ValueError(
                    "rank must be >= 1."
                )
        self.rank = rank
        self.updated_at = _utc_now_iso()
    # ========================================================
    # Lineage
    # ========================================================
    def add_parent(
        self,
        parent: "AlphaGenomeV393",
    ) -> None:
        """
        添加 parent lineage。
        """
        if not isinstance(
            parent,
            AlphaGenomeV393,
        ):
            raise TypeError(
                "parent must be AlphaGenome."
            )
        self.parent_ids = tuple(
            list(self.parent_ids)
            + [parent.genome_id]
        )
        self.parent_expression_hashes = (
            tuple(
                list(
                    self.parent_expression_hashes
                )
                + [parent.expression_hash]
            )
        )
        self.updated_at = _utc_now_iso()
    # ========================================================
    # Child creation
    # ========================================================
    def clone(
        self,
        *,
        new_genome_id: bool = True,
        generation: Optional[int] = None,
        reset_fitness: bool = False,
        metadata_update: Optional[
            Mapping[str, Any]
        ] = None,
    ) -> "AlphaGenomeV393":
        """
        创建当前 Genome 的副本。
        mutation / crossover 可以基于这个方法
        创建下一代 Genome。
        注意：
            默认不会修改当前 Genome。
        """
        metadata = dict(
            self.metadata
        )
        if metadata_update:
            metadata.update(
                metadata_update
            )
        clone = replace(
            self,
            genome_id=(
                uuid4().hex
                if new_genome_id
                else self.genome_id
            ),
            generation=(
                self.generation
                if generation is None
                else int(generation)
            ),
            metadata=metadata,
            created_at=_utc_now_iso(),
            updated_at=_utc_now_iso(),
        )
        if reset_fitness:
            clone.reset_evaluation()
        return clone
    def create_child(
        self,
        expression: AlphaExpression,
        *,
        generation: Optional[int] = None,
        mutation_type: Optional[str] = None,
        crossover_type: Optional[str] = None,
        parents: Optional[
            tuple["AlphaGenomeV393", ...]
        ] = None,
        metadata: Optional[
            Mapping[str, Any]
        ] = None,
    ) -> "AlphaGenomeV393":
        """
        根据新的 expression 创建 child Genome。
        这是 mutation / crossover 推荐使用的接口。
        """
        if not isinstance(
            expression,
            AlphaExpression,
        ):
            raise TypeError(
                "expression must be "
                "AlphaExpression."
            )
        parent_genomes = (
            parents
            if parents is not None
            else (self,)
        )
        parent_ids = tuple(
            parent.genome_id
            for parent in parent_genomes
        )
        parent_hashes = tuple(
            parent.expression_hash
            for parent in parent_genomes
        )
        child_generation = (
            self.generation + 1
            if generation is None
            else int(generation)
        )
        child_metadata = dict(
            metadata or {}
        )
        child_metadata.setdefault(
            "parent_count",
            len(parent_genomes),
        )
        return AlphaGenomeV393(
            expression=expression,
            generation=child_generation,
            parent_ids=parent_ids,
            parent_expression_hashes=(
                parent_hashes
            ),
            mutation_type=mutation_type,
            crossover_type=crossover_type,
            metadata=child_metadata,
        )
    # ========================================================
    # Evaluation reset
    # ========================================================
    def reset_evaluation(self) -> None:
        """
        重置所有评价状态。
        当 expression 被 mutation / crossover 修改后，
        必须重新 evaluation。
        """
        self.fitness = DEFAULT_FITNESS
        self.rank = None
        self.selected = False
        self.elite = False
        self.ic = float("nan")
        self.icir = float("nan")
        self.quantile_spread = float(
            "nan"
        )
        self.long_short_spread = float(
            "nan"
        )
        self.hit_rate = float("nan")
        self.turnover = float("nan")
        self.volatility = float("nan")
        self.sharpe = float("nan")
        self.max_drawdown = float(
            "nan"
        )
        self.complexity = float("nan")
        self.node_count = (
            self.expression.node_count()
        )
        self.depth = (
            self.expression.depth()
        )
        self.max_correlation = float(
            "nan"
        )
        self.mean_correlation = float(
            "nan"
        )
        self.correlation_penalty = 0.0
        self.oos_ic = float("nan")
        self.oos_icir = float("nan")
        self.oos_quantile_spread = float(
            "nan"
        )
        self.oos_turnover = float("nan")
        self.oos_passed = False
        self.updated_at = _utc_now_iso()
    # ========================================================
    # Serialization
    # ========================================================
    def to_dict(
        self,
        *,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """
        转换为 JSON-compatible dict。
        """
        result: dict[str, Any] = {
            "genome_version": (
                self.genome_version
            ),
            "genome_id": self.genome_id,
            "expression": (
                self.expression.to_dict()
            ),
            "expression_string": (
                self.expression_string
            ),
            "canonical_expression": (
                self.canonical_expression
            ),
            "expression_hash": (
                self.expression_hash
            ),
            "generation": self.generation,
            "fitness": self.fitness,
            "rank": self.rank,
            "selected": self.selected,
            "elite": self.elite,
            "ic": self.ic,
            "icir": self.icir,
            "quantile_spread": (
                self.quantile_spread
            ),
            "long_short_spread": (
                self.long_short_spread
            ),
            "hit_rate": self.hit_rate,
            "turnover": self.turnover,
            "volatility": self.volatility,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "complexity": self.complexity,
            "node_count": self.node_count,
            "depth": self.depth,
            "max_correlation": (
                self.max_correlation
            ),
            "mean_correlation": (
                self.mean_correlation
            ),
            "correlation_penalty": (
                self.correlation_penalty
            ),
            "oos_ic": self.oos_ic,
            "oos_icir": self.oos_icir,
            "oos_quantile_spread": (
                self.oos_quantile_spread
            ),
            "oos_turnover": (
                self.oos_turnover
            ),
            "oos_passed": self.oos_passed,
            "parent_ids": list(
                self.parent_ids
            ),
            "parent_expression_hashes": list(
                self.parent_expression_hashes
            ),
            "mutation_type": (
                self.mutation_type
            ),
            "crossover_type": (
                self.crossover_type
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_metadata:
            result["metadata"] = dict(
                self.metadata
            )
        return result
    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "AlphaGenomeV393":
        """
        从 dict 恢复 AlphaGenomeV393。
        """
        if not isinstance(
            data,
            Mapping,
        ):
            raise TypeError(
                "Genome data must be a mapping."
            )
        expression_data = data.get(
            "expression"
        )
        if expression_data is None:
            raise ValueError(
                "Genome data is missing "
                "'expression'."
            )
        expression = (
            AlphaExpression.from_dict(
                dict(expression_data)
            )
        )
        return cls(
            genome_id=str(
                data.get(
                    "genome_id",
                    uuid4().hex,
                )
            ),
            expression=expression,
            generation=_safe_int(
                data.get(
                    "generation",
                    0,
                )
            ),
            fitness=_safe_float(
                data.get(
                    "fitness",
                    DEFAULT_FITNESS,
                ),
                DEFAULT_FITNESS,
            ),
            rank=(
                None
                if data.get("rank") is None
                else _safe_int(
                    data.get("rank")
                )
            ),
            selected=bool(
                data.get(
                    "selected",
                    False,
                )
            ),
            elite=bool(
                data.get(
                    "elite",
                    False,
                )
            ),
            ic=_safe_float(
                data.get("ic")
            ),
            icir=_safe_float(
                data.get("icir")
            ),
            quantile_spread=_safe_float(
                data.get(
                    "quantile_spread"
                )
            ),
            long_short_spread=_safe_float(
                data.get(
                    "long_short_spread"
                )
            ),
            hit_rate=_safe_float(
                data.get(
                    "hit_rate"
                )
            ),
            turnover=_safe_float(
                data.get(
                    "turnover"
                )
            ),
            volatility=_safe_float(
                data.get(
                    "volatility"
                )
            ),
            sharpe=_safe_float(
                data.get(
                    "sharpe"
                )
            ),
            max_drawdown=_safe_float(
                data.get(
                    "max_drawdown"
                )
            ),
            complexity=_safe_float(
                data.get(
                    "complexity"
                )
            ),
            node_count=_safe_int(
                data.get(
                    "node_count",
                    expression.node_count(),
                )
            ),
            depth=_safe_int(
                data.get(
                    "depth",
                    expression.depth(),
                )
            ),
            max_correlation=_safe_float(
                data.get(
                    "max_correlation"
                )
            ),
            mean_correlation=_safe_float(
                data.get(
                    "mean_correlation"
                )
            ),
            correlation_penalty=_safe_float(
                data.get(
                    "correlation_penalty",
                    0.0,
                ),
                0.0,
            ),
            oos_ic=_safe_float(
                data.get(
                    "oos_ic"
                )
            ),
            oos_icir=_safe_float(
                data.get(
                    "oos_icir"
                )
            ),
            oos_quantile_spread=_safe_float(
                data.get(
                    "oos_quantile_spread"
                )
            ),
            oos_turnover=_safe_float(
                data.get(
                    "oos_turnover"
                )
            ),
            oos_passed=bool(
                data.get(
                    "oos_passed",
                    False,
                )
            ),
            parent_ids=tuple(
                str(x)
                for x in data.get(
                    "parent_ids",
                    [],
                )
            ),
            parent_expression_hashes=tuple(
                str(x)
                for x in data.get(
                    "parent_expression_hashes",
                    [],
                )
            ),
            mutation_type=data.get(
                "mutation_type"
            ),
            crossover_type=data.get(
                "crossover_type"
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
            ),
            created_at=str(
                data.get(
                    "created_at",
                    _utc_now_iso(),
                )
            ),
            updated_at=str(
                data.get(
                    "updated_at",
                    _utc_now_iso(),
                )
            ),
            genome_version=str(
                data.get(
                    "genome_version",
                    GENOME_VERSION,
                )
            ),
        )
    # ========================================================
    # Comparison helpers
    # ========================================================
    def fitness_key(self) -> float:
        """
        用于排序的 fitness。
        NaN / -inf 统一视为极低值。
        """
        import math
        if not math.isfinite(
            self.fitness
        ):
            return float("-inf")
        return self.fitness
    def __lt__(
        self,
        other: object,
    ) -> bool:
        if not isinstance(
            other,
            AlphaGenomeV393,
        ):
            return NotImplemented
        return (
            self.fitness_key()
            < other.fitness_key()
        )
    # ========================================================
    # Summary
    # ========================================================
    def summary(self) -> dict[str, Any]:
        """
        返回适合日志/终端输出的摘要。
        """
        return {
            "genome_id": self.genome_id,
            "generation": self.generation,
            "expression": self.expression_string,
            "fitness": self.fitness,
            "ic": self.ic,
            "icir": self.icir,
            "q5_q1": self.quantile_spread,
            "turnover": self.turnover,
            "complexity": self.complexity,
            "oos_ic": self.oos_ic,
            "oos_passed": self.oos_passed,
            "elite": self.elite,
        }
    def __str__(self) -> str:
        return (
            f"AlphaGenomeV393("
            f"id={self.genome_id[:8]}, "
            f"generation={self.generation}, "
            f"fitness={self.fitness:.6g}, "
            f"expression={self.expression_string}"
            f")"
        )
# ============================================================
# Factory functions
# ============================================================
def genome_from_expression(
    expression: AlphaExpression,
    *,
    generation: int = 0,
    metadata: Optional[
        Mapping[str, Any]
    ] = None,
) -> AlphaGenomeV393:
    """
    从 AlphaExpression 创建 Genome。
    """
    return AlphaGenomeV393(
        expression=expression,
        generation=generation,
        metadata=dict(
            metadata or {}
        ),
    )
def clone_genome(
    genome: AlphaGenomeV393,
    *,
    generation: Optional[int] = None,
    reset_fitness: bool = False,
) -> AlphaGenomeV393:
    """
    Genome clone helper。
    """
    return genome.clone(
        generation=generation,
        reset_fitness=reset_fitness,
    )
def create_child_genome(
    parent: AlphaGenomeV393,
    expression: AlphaExpression,
    *,
    generation: Optional[int] = None,
    mutation_type: Optional[str] = None,
    crossover_type: Optional[str] = None,
    parents: Optional[
        tuple[AlphaGenomeV393, ...]
    ] = None,
    metadata: Optional[
        Mapping[str, Any]
    ] = None,
) -> AlphaGenomeV393:
    """
    创建下一代 Genome。
    """
    return parent.create_child(
        expression=expression,
        generation=generation,
        mutation_type=mutation_type,
        crossover_type=crossover_type,
        parents=parents,
        metadata=metadata,
    )
# ============================================================
# Public exports
# ============================================================
__all__ = [
    "GENOME_VERSION",
    "DEFAULT_FITNESS",
    "DEFAULT_GENERATION",
    "AlphaGenomeV393",
    "genome_from_expression",
    "clone_genome",
    "create_child_genome",
]
