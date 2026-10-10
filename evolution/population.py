"""
AI Hedge Fund OS - V3.9.3
File: evolution/population.py
Alpha population management and evolutionary orchestration.
Responsibilities
----------------
1. Manage AlphaGenome objects.
2. Initialize populations from genomes or AlphaExpression objects.
3. Deduplicate genomes by canonical expression hash.
4. Rank genomes using actual fitness values.
5. Preserve elite genomes across generations.
6. Select parents using tournament or rank-based selection.
7. Generate offspring using crossover and mutation engines.
8. Introduce random immigrants to maintain diversity.
9. Track population diversity and generation statistics.
10. Serialize population state into JSON-compatible dictionaries.
Python: 3.11+
Important
---------
- This module does not calculate fitness or backtest results.
- Fitness must be supplied by the actual evaluation pipeline.
- This module does not place orders or connect to live trading APIs.
"""
from __future__ import annotations
import copy
import math
import random
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Iterator, Literal, Optional, Sequence
# V3.9.3 population 使用项目的 V3.9.2 表达式实现（AlphaExpressionV392）
# 与 V3.9.3 的 AlphaGenomeV393，统一以公有名引用。
from alpha.expression import (
    AlphaExpressionV392 as AlphaExpression,
)
from alpha.generator import (
    AlphaExpressionGenerator,
    AlphaGeneratorConfig,
)
from evolution.alpha_genome import (
    AlphaGenomeV393 as AlphaGenome,
    genome_from_expression,
)
from evolution.alpha_mutation import (
    AlphaMutationConfig,
    AlphaMutationEngine,
)
from evolution.alpha_crossover import (
    AlphaCrossoverConfig,
    AlphaCrossoverEngine,
)
SelectionMethod = Literal["tournament", "rank"]
class AlphaPopulationError(RuntimeError):
    """Base exception for population management errors."""
class InvalidPopulationError(AlphaPopulationError):
    """Raised when population configuration or contents are invalid."""
class EvolutionError(AlphaPopulationError):
    """Raised when the next generation cannot be created."""
@dataclass
class AlphaPopulationConfig:
    """Configuration for Alpha population management."""
    # Population size
    population_size: int = 100
    # Elitism
    elite_size: int = 10
    # Parent selection
    selection_method: SelectionMethod = "tournament"
    tournament_size: int = 3
    # Offspring generation probabilities
    crossover_rate: float = 0.70
    mutation_rate: float = 0.30
    immigrant_rate: float = 0.05
    # Expression constraints
    max_depth: int = 4
    max_nodes: int = 15
    # Population maintenance
    deduplicate: bool = True
    preserve_elites: bool = True
    retry_limit: int = 20
    # Randomness
    seed: int = 42
    # Optional expression-generator configuration
    generator_features: Optional[list[str]] = None
    def __post_init__(self) -> None:
        if self.population_size < 2:
            raise ValueError("population_size must be at least 2")
        if not 0 <= self.elite_size < self.population_size:
            raise ValueError(
                "elite_size must be >= 0 and smaller than population_size"
            )
        if self.tournament_size < 1:
            raise ValueError("tournament_size must be >= 1")
        if self.selection_method not in ("tournament", "rank"):
            raise ValueError(
                "selection_method must be 'tournament' or 'rank'"
            )
        for name, value in (
            ("crossover_rate", self.crossover_rate),
            ("mutation_rate", self.mutation_rate),
            ("immigrant_rate", self.immigrant_rate),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.crossover_rate + self.mutation_rate > 1.0 + 1e-12:
            raise ValueError(
                "crossover_rate + mutation_rate must not exceed 1.0"
            )
        if self.max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        if self.max_nodes < 1:
            raise ValueError("max_nodes must be >= 1")
        if self.retry_limit < 1:
            raise ValueError("retry_limit must be >= 1")
@dataclass
class PopulationStatistics:
    """JSON-compatible snapshot of population state."""
    generation: int
    size: int
    evaluated_count: int
    finite_fitness_count: int
    unique_expression_count: int
    unique_feature_count: int
    mean_fitness: Optional[float]
    median_fitness: Optional[float]
    best_fitness: Optional[float]
    worst_fitness: Optional[float]
    mean_complexity: Optional[float]
    expression_diversity: float
    feature_frequency: dict[str, int] = field(default_factory=dict)
    operator_frequency: dict[str, int] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
class AlphaPopulation:
    """
    Container and evolutionary coordinator for AlphaGenome instances.
    Parameters
    ----------
    genomes:
        Optional initial genomes.
    config:
        Population settings.
    mutation_engine:
        Optional preconfigured mutation engine.
    crossover_engine:
        Optional preconfigured crossover engine.
    generator:
        Optional expression generator for initial candidates/immigrants.
    """
    def __init__(
        self,
        genomes: Optional[Iterable[AlphaGenome]] = None,
        config: Optional[AlphaPopulationConfig] = None,
        mutation_engine: Optional[AlphaMutationEngine] = None,
        crossover_engine: Optional[AlphaCrossoverEngine] = None,
        generator: Optional[AlphaExpressionGenerator] = None,
    ) -> None:
        self.config = config or AlphaPopulationConfig()
        self._rng = random.Random(self.config.seed)
        self.generation = 0
        self.genomes: list[AlphaGenome] = []
        mutation_config = AlphaMutationConfig(
            max_depth=self.config.max_depth,
            max_nodes=self.config.max_nodes,
            seed=self.config.seed + 101,
        )
        crossover_config = AlphaCrossoverConfig(
            max_depth=self.config.max_depth,
            max_nodes=self.config.max_nodes,
            seed=self.config.seed + 202,
        )
        self.mutation_engine = mutation_engine or AlphaMutationEngine(
            mutation_config
        )
        self.crossover_engine = crossover_engine or AlphaCrossoverEngine(
            crossover_config
        )
        generator_config = AlphaGeneratorConfig(
            max_depth=self.config.max_depth,
            max_nodes=self.config.max_nodes,
            seed=self.config.seed + 303,
        )
        if self.config.generator_features:
            generator_config.features = list(self.config.generator_features)
        self.generator = generator or AlphaExpressionGenerator(
            generator_config
        )
        if genomes is not None:
            self.extend(genomes)
    # ------------------------------------------------------------------
    # Basic container interface
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.genomes)
    def __iter__(self) -> Iterator[AlphaGenome]:
        return iter(self.genomes)
    def __getitem__(self, index: int) -> AlphaGenome:
        return self.genomes[index]
    def __contains__(self, genome: object) -> bool:
        if not isinstance(genome, AlphaGenome):
            return False
        return any(item.genome_id == genome.genome_id for item in self.genomes)
    @property
    def size(self) -> int:
        return len(self.genomes)
    @property
    def is_empty(self) -> bool:
        return not self.genomes
    @property
    def unique_expression_count(self) -> int:
        return len({self._expression_key(g) for g in self.genomes})
    @property
    def evaluated_count(self) -> int:
        return sum(1 for g in self.genomes if g.is_evaluated)
    @property
    def best(self) -> Optional[AlphaGenome]:
        ranked = self.sorted_genomes()
        return ranked[0] if ranked else None
    # ------------------------------------------------------------------
    # Initialization and insertion
    # ------------------------------------------------------------------
    def initialize(
        self,
        expressions: Optional[Iterable[AlphaExpression]] = None,
        target_size: Optional[int] = None,
        include_base_features: bool = True,
    ) -> "AlphaPopulation":
        """
        Initialize or refill the population.
        Existing genomes are retained. If expressions are provided, they are
        inserted first. Random expressions are generated only when needed.
        """
        target = target_size or self.config.population_size
        if target < 1:
            raise ValueError("target_size must be >= 1")
        if expressions is not None:
            for expression in expressions:
                self.add(genome_from_expression(expression))
        attempts = 0
        max_attempts = max(target * self.config.retry_limit, 100)
        while len(self.genomes) < target and attempts < max_attempts:
            attempts += 1
            missing = max(target - len(self.genomes), 1)
            try:
                generated = self.generator.generate_candidates(
                    missing,
                    include_base_features=include_base_features,
                    deduplicate=True,
                )
            except TypeError:
                # Compatibility fallback for generators with a simpler API.
                generated = self.generator.generate_candidates(missing)
            if not generated:
                continue
            for candidate in generated:
                if isinstance(candidate, AlphaGenome):
                    genome = candidate
                elif isinstance(candidate, AlphaExpression):
                    genome = genome_from_expression(candidate)
                else:
                    raise InvalidPopulationError(
                        "Generator must return AlphaExpression or AlphaGenome"
                    )
                self.add(genome)
                if len(self.genomes) >= target:
                    break
        if len(self.genomes) < target:
            raise EvolutionError(
                f"Could only initialize {len(self.genomes)} unique genomes; "
                f"target was {target}. Consider relaxing expression "
                "constraints or disabling deduplication."
            )
        self._trim_to_size(target)
        return self
    def add(
        self,
        genome: AlphaGenome,
        replace_duplicate: bool = True,
    ) -> bool:
        """
        Add one genome.
        Returns True if the population changed, otherwise False.
        With deduplication enabled, duplicate expressions are identified by
        canonical expression hash.
        """
        if not isinstance(genome, AlphaGenome):
            raise TypeError("genome must be an AlphaGenome instance")
        self._validate_genome(genome)
        if self.config.deduplicate:
            key = self._expression_key(genome)
            for index, existing in enumerate(self.genomes):
                if self._expression_key(existing) != key:
                    continue
                if not replace_duplicate:
                    return False
                if self._fitness_sort_key(genome) > self._fitness_sort_key(
                    existing
                ):
                    self.genomes[index] = genome
                    return True
                return False
        self.genomes.append(genome)
        return True
    def extend(self, genomes: Iterable[AlphaGenome]) -> int:
        """Add multiple genomes and return the number successfully added."""
        added = 0
        for genome in genomes:
            if self.add(genome):
                added += 1
        return added
    def remove(self, genome: AlphaGenome) -> bool:
        """Remove a genome by genome_id."""
        for index, existing in enumerate(self.genomes):
            if existing.genome_id == genome.genome_id:
                del self.genomes[index]
                return True
        return False
    def clear(self) -> None:
        """Remove all genomes from the population."""
        self.genomes.clear()
    def initialize_from_dicts(
        self,
        records: Iterable[dict[str, Any]],
        deduplicate: Optional[bool] = None,
    ) -> int:
        """Load serialized genomes from dictionaries."""
        previous = self.config.deduplicate
        if deduplicate is not None:
            self.config.deduplicate = deduplicate
        try:
            loaded = [AlphaGenome.from_dict(record) for record in records]
            return self.extend(loaded)
        finally:
            self.config.deduplicate = previous
    # ------------------------------------------------------------------
    # Ranking and selection
    # ------------------------------------------------------------------
    @staticmethod
    def _valid_fitness(genome: AlphaGenome) -> Optional[float]:
        try:
            value = float(genome.fitness)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(value):
            return None
        return value
    @classmethod
    def _fitness_sort_key(cls, genome: AlphaGenome) -> tuple[int, float]:
        """
        Higher fitness ranks first.
        Non-finite fitness is always ranked below finite fitness.
        This method does not manufacture a score for unevaluated genomes.
        """
        value = cls._valid_fitness(genome)
        if value is None:
            return (0, float("-inf"))
        return (1, value)
    @staticmethod
    def _expression_key(genome: AlphaGenome) -> str:
        return str(genome.expression_hash)
    def _validate_genome(self, genome: AlphaGenome) -> None:
        if not isinstance(genome.expression, AlphaExpression):
            raise InvalidPopulationError(
                f"Genome {genome.genome_id} has an invalid expression"
            )
        genome.expression.validate(
            max_depth=self.config.max_depth,
            max_nodes=self.config.max_nodes,
        )
    def sorted_genomes(
        self,
        evaluated_only: bool = False,
        descending: bool = True,
    ) -> list[AlphaGenome]:
        """Return a sorted copy without modifying population order."""
        items = list(self.genomes)
        if evaluated_only:
            items = [
                g for g in items if self._valid_fitness(g) is not None
            ]
        return sorted(
            items,
            key=self._fitness_sort_key,
            reverse=descending,
        )
    def assign_ranks(self) -> None:
        """Assign rank values in-place; rank 1 is the best."""
        ranked = self.sorted_genomes()
        for rank, genome in enumerate(ranked, start=1):
            genome.set_rank(rank)
    def top_k(
        self,
        k: int,
        evaluated_only: bool = False,
    ) -> list[AlphaGenome]:
        if k < 0:
            raise ValueError("k must be >= 0")
        return self.sorted_genomes(evaluated_only=evaluated_only)[:k]
    def select_elites(
        self,
        elite_size: Optional[int] = None,
    ) -> list[AlphaGenome]:
        """Return the highest-ranked genomes without changing the population."""
        count = self.config.elite_size if elite_size is None else elite_size
        if count < 0:
            raise ValueError("elite_size must be >= 0")
        elites = self.sorted_genomes()[:count]
        elite_ids = {g.genome_id for g in elites}
        for genome in self.genomes:
            genome.mark_elite(genome.genome_id in elite_ids)
        return elites
    def select_parent(
        self,
        method: Optional[SelectionMethod] = None,
    ) -> AlphaGenome:
        """
        Select one parent.
        If no genome has finite fitness, selection falls back to uniform
        random selection instead of fabricating fitness values.
        """
        if not self.genomes:
            raise InvalidPopulationError("Cannot select from an empty population")
        method = method or self.config.selection_method
        if method not in ("tournament", "rank"):
            raise ValueError("Unsupported selection method")
        eligible = self.sorted_genomes(evaluated_only=True)
        if not eligible:
            return self._rng.choice(self.genomes)
        if method == "tournament":
            pool_size = min(self.config.tournament_size, len(eligible))
            contestants = self._rng.sample(eligible, pool_size)
            return max(contestants, key=self._fitness_sort_key)
        # Rank selection: better ranks receive greater sampling probability.
        ranked = eligible
        weights = list(range(len(ranked), 0, -1))
        return self._rng.choices(ranked, weights=weights, k=1)[0]
    def select_parents(
        self,
        count: int,
        method: Optional[SelectionMethod] = None,
    ) -> list[AlphaGenome]:
        if count < 0:
            raise ValueError("count must be >= 0")
        return [self.select_parent(method) for _ in range(count)]
    # ------------------------------------------------------------------
    # Deduplication and diversity
    # ------------------------------------------------------------------
    def deduplicate_population(self) -> int:
        """
        Deduplicate by canonical expression hash.
        When duplicates have different fitness values, keep the better one.
        For equally scored or unevaluated duplicates, preserve the first.
        Returns the number of removed genomes.
        """
        before = len(self.genomes)
        best_by_key: dict[str, AlphaGenome] = {}
        for genome in self.genomes:
            key = self._expression_key(genome)
            existing = best_by_key.get(key)
            if existing is None:
                best_by_key[key] = genome
            elif self._fitness_sort_key(genome) > self._fitness_sort_key(
                existing
            ):
                best_by_key[key] = genome
        self.genomes = list(best_by_key.values())
        return before - len(self.genomes)
    def diversity(self) -> dict[str, Any]:
        """Return expression-level and feature-level diversity statistics."""
        if not self.genomes:
            return {
                "size": 0,
                "unique_expressions": 0,
                "expression_diversity": 0.0,
                "unique_features": 0,
                "feature_frequency": {},
                "operator_frequency": {},
            }
        expression_keys = [self._expression_key(g) for g in self.genomes]
        unique_expressions = len(set(expression_keys))
        feature_frequency: Counter[str] = Counter()
        operator_frequency: Counter[str] = Counter()
        for genome in self.genomes:
            feature_frequency.update(genome.feature_names)
            try:
                nodes = self._walk_expression(genome.expression)
                operator_frequency.update(
                    node.operator
                    for node in nodes
                    if node.is_operator and node.operator is not None
                )
            except (AttributeError, TypeError):
                # Feature and expression diversity remain available even if
                # a custom expression implementation lacks a tree iterator.
                pass
        return {
            "size": len(self.genomes),
            "unique_expressions": unique_expressions,
            "expression_diversity": unique_expressions / len(self.genomes),
            "unique_features": len(feature_frequency),
            "feature_frequency": dict(feature_frequency.most_common()),
            "operator_frequency": dict(operator_frequency.most_common()),
        }
    @staticmethod
    def _walk_expression(
        expression: AlphaExpression,
    ) -> Iterator[AlphaExpression]:
        yield expression
        for child in expression.children:
            yield from AlphaPopulation._walk_expression(child)
    # ------------------------------------------------------------------
    # Generation evolution
    # ------------------------------------------------------------------
    def create_next_generation(
        self,
        population_size: Optional[int] = None,
        generation: Optional[int] = None,
    ) -> "AlphaPopulation":
        """
        Create the next generation.
        Process:
        1. Preserve elite genomes.
        2. Generate crossover offspring.
        3. Generate mutation offspring.
        4. Generate random immigrants.
        5. Fill any remaining slots.
        6. Deduplicate and enforce population size.
        Fitness for new offspring is reset and must be recalculated by the
        fitness/evaluation pipeline.
        """
        if not self.genomes:
            raise InvalidPopulationError(
                "Cannot evolve an empty population; initialize it first"
            )
        target_size = population_size or self.config.population_size
        if target_size < 2:
            raise ValueError("population_size must be >= 2")
        next_generation_number = (
            self.generation + 1 if generation is None else generation
        )
        if next_generation_number <= self.generation:
            raise ValueError("generation must be greater than current generation")
        next_genomes: list[AlphaGenome] = []
        seen: set[str] = set()
        def add_candidate(
            candidate: AlphaGenome,
            *,
            allow_duplicate: bool = False,
        ) -> bool:
            try:
                self._validate_genome(candidate)
            except (ValueError, TypeError, AttributeError):
                return False
            key = self._expression_key(candidate)
            if self.config.deduplicate and not allow_duplicate and key in seen:
                return False
            next_genomes.append(candidate)
            seen.add(key)
            return True
        # 1. Elite preservation.
        if self.config.preserve_elites and self.config.elite_size > 0:
            elite_count = min(
                self.config.elite_size,
                target_size - 1,
                len(self.genomes),
            )
            for elite in self.select_elites(elite_count):
                clone = self._clone_for_next_generation(
                    elite,
                    generation=next_generation_number,
                    preserve_fitness=True,
                )
                add_candidate(clone)
        # 2. Determine immigrant budget.
        immigrant_count = min(
            target_size - len(next_genomes),
            int(round(target_size * self.config.immigrant_rate)),
        )
        # Reserve immigrant slots first so crossover/mutation do not crowd
        # out the configured diversity budget.
        offspring_target = target_size - immigrant_count
        # 3. Produce offspring.
        attempts = 0
        max_attempts = target_size * self.config.retry_limit
        while len(next_genomes) < offspring_target and attempts < max_attempts:
            attempts += 1
            draw = self._rng.random()
            try:
                if (
                    draw < self.config.crossover_rate
                    and len(self.genomes) >= 2
                ):
                    parent_a = self.select_parent()
                    parent_b = self.select_parent()
                    if (
                        self.config.deduplicate
                        and len(self.genomes) > 1
                        and parent_a.genome_id == parent_b.genome_id
                    ):
                        alternatives = [
                            g for g in self.genomes
                            if g.genome_id != parent_a.genome_id
                        ]
                        if alternatives:
                            parent_b = self._rng.choice(alternatives)
                    children = self.crossover_engine.crossover(
                        parent_a,
                        parent_b,
                        generation=next_generation_number,
                    )
                    if not children:
                        continue
                    for child in children:
                        self._reset_child(
                            child,
                            generation=next_generation_number,
                        )
                        add_candidate(child)
                        if len(next_genomes) >= offspring_target:
                            break
                elif draw < (
                    self.config.crossover_rate + self.config.mutation_rate
                ):
                    parent = self.select_parent()
                    child = self.mutation_engine.mutate(
                        parent,
                        generation=next_generation_number,
                    )
                    self._reset_child(
                        child,
                        generation=next_generation_number,
                    )
                    add_candidate(child)
                else:
                    # The residual probability creates a fresh candidate.
                    immigrant = self._make_random_genome(
                        generation=next_generation_number
                    )
                    add_candidate(immigrant)
            except (ValueError, TypeError, RuntimeError, AttributeError):
                # Invalid genetic operations are skipped and retried.
                # No fabricated genome or fitness is inserted.
                continue
        # 4. Fill the immigrant budget.
        attempts = 0
        while (
            len(next_genomes) < target_size
            and attempts < max_attempts
        ):
            attempts += 1
            try:
                immigrant = self._make_random_genome(
                    generation=next_generation_number
                )
                if not add_candidate(immigrant):
                    continue
            except (ValueError, TypeError, RuntimeError, AttributeError):
                continue
        # 5. If constraints or aggressive deduplication prevented filling
        # the target, retain valid parent genomes as a safe fallback.
        if len(next_genomes) < target_size:
            for parent in self.sorted_genomes():
                if len(next_genomes) >= target_size:
                    break
                fallback = self._clone_for_next_generation(
                    parent,
                    generation=next_generation_number,
                    preserve_fitness=True,
                )
                add_candidate(fallback, allow_duplicate=True)
        if not next_genomes:
            raise EvolutionError(
                "Evolution produced no valid genomes. Check expression "
                "constraints and mutation/crossover configuration."
            )
        # Deduplication can leave the population smaller than requested.
        # Duplicate fallback clones are allowed only as a last resort.
        fallback_index = 0
        parents_ranked = self.sorted_genomes()
        while len(next_genomes) < target_size and parents_ranked:
            parent = parents_ranked[fallback_index % len(parents_ranked)]
            fallback_index += 1
            fallback = self._clone_for_next_generation(
                parent,
                generation=next_generation_number,
                preserve_fitness=True,
            )
            add_candidate(fallback, allow_duplicate=True)
        result = AlphaPopulation(
            genomes=next_genomes[:target_size],
            config=copy.deepcopy(self.config),
            mutation_engine=self.mutation_engine,
            crossover_engine=self.crossover_engine,
            generator=self.generator,
        )
        result.generation = next_generation_number
        result.assign_ranks()
        return result
    def evolve_one_generation(self) -> "AlphaPopulation":
        """Alias for create_next_generation()."""
        return self.create_next_generation()
    def _make_random_genome(self, generation: int) -> AlphaGenome:
        generated = self.generator.generate_candidates(
            1,
            include_base_features=False,
            deduplicate=True,
        )
        if not generated:
            raise EvolutionError("Expression generator returned no candidates")
        candidate = generated[0]
        if isinstance(candidate, AlphaGenome):
            genome = candidate
        elif isinstance(candidate, AlphaExpression):
            genome = genome_from_expression(candidate)
        else:
            raise EvolutionError(
                "Generator must return AlphaExpression or AlphaGenome"
            )
        genome.generation = generation
        self._reset_child(genome, generation)
        return genome
    @staticmethod
    def _reset_child(
        genome: AlphaGenome,
        generation: int,
    ) -> None:
        """
        Reset evaluation state for offspring.
        The reset_evaluation method belongs to AlphaGenome and is responsible
        for clearing metrics and fitness consistently.
        """
        genome.generation = generation
        reset_method = getattr(genome, "reset_evaluation", None)
        if callable(reset_method):
            reset_method()
        # Guard against custom Genome implementations that do not reset all
        # required evaluation fields.
        genome.fitness = float("-inf")
        genome.rank = None
        genome.selected = False
        genome.elite = False
    @staticmethod
    def _clone_for_next_generation(
        genome: AlphaGenome,
        generation: int,
        preserve_fitness: bool,
    ) -> AlphaGenome:
        """Clone a genome without sharing mutable metadata with its parent."""
        clone = copy.deepcopy(genome)
        parent_id = str(genome.genome_id)
        clone.genome_id = uuid.uuid4().hex
        clone.generation = generation
        clone.parent_ids = [parent_id]
        clone.parent_expression_hashes = [str(genome.expression_hash)]
        clone.selected = False
        clone.elite = False
        clone.rank = None
        if not preserve_fitness:
            AlphaPopulation._reset_child(clone, generation)
        return clone
    def _trim_to_size(self, target_size: int) -> None:
        if len(self.genomes) <= target_size:
            return
        self.genomes = self.sorted_genomes()[:target_size]
    # ------------------------------------------------------------------
    # Evaluation integration
    # ------------------------------------------------------------------
    def update_genome_fitness(
        self,
        genome_id: str,
        fitness: float,
        **metrics: Any,
    ) -> bool:
        """
        Update one genome using externally calculated fitness and metrics.
        Fitness evaluation is intentionally external. This method only stores
        the results produced by the real Alpha fitness evaluator.
        """
        genome = next(
            (g for g in self.genomes if g.genome_id == genome_id),
            None,
        )
        if genome is None:
            return False
        genome.update_fitness(fitness=fitness, **metrics)
        return True
    def update_genome_oos(
        self,
        genome_id: str,
        **metrics: Any,
    ) -> bool:
        """Attach out-of-sample validation results to a genome."""
        genome = next(
            (g for g in self.genomes if g.genome_id == genome_id),
            None,
        )
        if genome is None:
            return False
        genome.update_oos(**metrics)
        return True
    # ------------------------------------------------------------------
    # Statistics and serialization
    # ------------------------------------------------------------------
    def statistics(self) -> PopulationStatistics:
        """Calculate descriptive statistics from current population state."""
        values = [
            value
            for genome in self.genomes
            if (value := self._valid_fitness(genome)) is not None
        ]
        complexities: list[float] = []
        for genome in self.genomes:
            try:
                complexities.append(float(genome.complexity))
            except (TypeError, ValueError, AttributeError):
                complexities.append(float(genome.node_count))
        diversity = self.diversity()
        mean_fitness: Optional[float] = None
        median_fitness: Optional[float] = None
        best_fitness: Optional[float] = None
        worst_fitness: Optional[float] = None
        mean_complexity: Optional[float] = None
        if values:
            ordered = sorted(values)
            count = len(ordered)
            mean_fitness = sum(ordered) / count
            midpoint = count // 2
            if count % 2:
                median_fitness = ordered[midpoint]
            else:
                median_fitness = (
                    ordered[midpoint - 1] + ordered[midpoint]
                ) / 2.0
            best_fitness = ordered[-1]
            worst_fitness = ordered[0]
        if complexities:
            mean_complexity = sum(complexities) / len(complexities)
        return PopulationStatistics(
            generation=self.generation,
            size=len(self.genomes),
            evaluated_count=self.evaluated_count,
            finite_fitness_count=len(values),
            unique_expression_count=diversity["unique_expressions"],
            unique_feature_count=diversity["unique_features"],
            mean_fitness=mean_fitness,
            median_fitness=median_fitness,
            best_fitness=best_fitness,
            worst_fitness=worst_fitness,
            mean_complexity=mean_complexity,
            expression_diversity=diversity["expression_diversity"],
            feature_frequency=diversity["feature_frequency"],
            operator_frequency=diversity["operator_frequency"],
        )
    def to_dict(self) -> dict[str, Any]:
        """Serialize the population into a JSON-compatible dictionary."""
        return {
            "schema_version": "3.9.3",
            "generation": self.generation,
            "config": asdict(self.config),
            "genomes": [genome.to_dict() for genome in self.genomes],
            "statistics": self.statistics().to_dict(),
        }
    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        config: Optional[AlphaPopulationConfig] = None,
    ) -> "AlphaPopulation":
        """Restore a population from a dictionary produced by to_dict()."""
        if not isinstance(data, dict):
            raise TypeError("Population data must be a dictionary")
        if config is None:
            raw_config = data.get("config", {})
            allowed_fields = set(AlphaPopulationConfig.__dataclass_fields__)
            clean_config = {
                key: value
                for key, value in raw_config.items()
                if key in allowed_fields
            }
            config = AlphaPopulationConfig(**clean_config)
        raw_genomes = data.get("genomes", [])
        genomes = [
            AlphaGenome.from_dict(item)
            for item in raw_genomes
        ]
        population = cls(genomes=genomes, config=config)
        population.generation = int(data.get("generation", 0))
        population.assign_ranks()
        return population
    def summary(self) -> dict[str, Any]:
        """Compact operational summary for logs and CLI output."""
        stats = self.statistics()
        best = self.best
        return {
            "generation": self.generation,
            "population_size": len(self.genomes),
            "evaluated_count": stats.evaluated_count,
            "unique_expression_count": stats.unique_expression_count,
            "expression_diversity": round(
                stats.expression_diversity, 4
            ),
            "best_genome_id": best.genome_id if best else None,
            "best_expression": best.expression_string if best else None,
            "best_fitness": (
                self._valid_fitness(best) if best is not None else None
            ),
        }
    def __repr__(self) -> str:
        return (
            f"AlphaPopulation("
            f"generation={self.generation}, "
            f"size={len(self.genomes)}, "
            f"unique={self.unique_expression_count})"
        )
# ----------------------------------------------------------------------
# Functional helpers
# ----------------------------------------------------------------------
def create_population(
    expressions: Optional[Iterable[AlphaExpression]] = None,
    population_size: int = 100,
    seed: int = 42,
    config: Optional[AlphaPopulationConfig] = None,
) -> AlphaPopulation:
    """Convenience function for creating an initialized population."""
    resolved_config = config or AlphaPopulationConfig(
        population_size=population_size,
        seed=seed,
    )
    population = AlphaPopulation(config=resolved_config)
    return population.initialize(
        expressions=expressions,
        target_size=resolved_config.population_size,
    )
def evolve_population(
    population: AlphaPopulation,
    generations: int = 1,
) -> AlphaPopulation:
    """
    Apply evolutionary operators repeatedly.
    Note: fitness evaluation is not performed here. The caller should evaluate
    each newly created generation before evolving it again.
    """
    if generations < 0:
        raise ValueError("generations must be >= 0")
    current = population
    for _ in range(generations):
        current = current.create_next_generation()
    return current
__all__ = [
    "AlphaPopulationError",
    "InvalidPopulationError",
    "EvolutionError",
    "AlphaPopulationConfig",
    "PopulationStatistics",
    "AlphaPopulation",
    "create_population",
    "evolve_population",
]
