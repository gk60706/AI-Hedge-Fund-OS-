from __future__ import annotations


class FactorRegistry:
    def __init__(
        self,
    ):
        self._factors = {}

    def register(
        self,
        factor,
    ):
        self._factors[factor.name] = factor

    def get(
        self,
        name: str,
    ):
        return self._factors.get(name)

    def all(
        self,
    ):
        return list(self._factors.values())


# ============================================================================
# V3.9.2 step15 - Factor Registry
# ============================================================================
import hashlib as _hashlib_v392
import json as _json_v392
import logging as _logging_v392
import re as _re_v392
from dataclasses import (
    asdict as _asdict_v392,
    dataclass as _dataclass_v392,
    field as _field_v392,
)
from pathlib import Path as _PathV392
from typing import (
    Any as _AnyV392,
    Dict as _DictV392,
    Iterable as _IterableV392,
    List as _ListV392,
    Optional as _OptV392,
    Sequence as _SeqV392,
)

from .base import (
    BaseFactorV392,
    FactorConfigV392,
    FactorDirectionV392,
    FactorScopeV392,
)

_logger_v392 = _logging_v392.getLogger(__name__)


class FactorRegistryErrorV392(Exception):
    """Factor Registry 基础异常。"""


class FactorAlreadyExistsErrorV392(FactorRegistryErrorV392):
    """因子已经存在。"""


class FactorNotFoundErrorV392(FactorRegistryErrorV392):
    """找不到因子。"""


class FactorAliasConflictErrorV392(FactorRegistryErrorV392):
    """Alias 冲突。"""


from enum import Enum as _EnumV392


class FactorFamilyV392(str, _EnumV392):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    VALUE = "value"
    QUALITY = "quality"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    RISK = "risk"
    LIQUIDITY = "liquidity"
    OTHER = "other"


@_dataclass_v392
class FactorDescriptorV392:
    """Factor Registry 中的因子描述。"""

    name: str
    family: FactorFamilyV392
    version: str
    description: str
    factor: BaseFactorV392 = _field_v392(repr=False)
    tags: _ListV392[str] = _field_v392(default_factory=list)
    aliases: _ListV392[str] = _field_v392(default_factory=list)
    scope: str = ""
    direction: str = ""
    lookback: _OptV392[int] = None
    requires_pit: bool = False
    required_columns: _ListV392[str] = _field_v392(default_factory=list)
    metadata: _DictV392[str, _AnyV392] = _field_v392(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = str(self.name).strip()
        self.version = str(self.version).strip()
        self.tags = sorted(
            {
                str(x).strip().lower()
                for x in self.tags
                if str(x).strip()
            }
        )
        self.aliases = sorted(
            {
                str(x).strip().lower()
                for x in self.aliases
                if str(x).strip()
            }
        )
        self.required_columns = sorted(
            {
                str(x).strip()
                for x in self.required_columns
                if str(x).strip()
            }
        )

    def public_metadata(self) -> _DictV392[str, _AnyV392]:
        return {
            "name": self.name,
            "family": self.family.value,
            "version": self.version,
            "description": self.description,
            "tags": list(self.tags),
            "aliases": list(self.aliases),
            "scope": self.scope,
            "direction": self.direction,
            "lookback": self.lookback,
            "requires_pit": self.requires_pit,
            "required_columns": list(self.required_columns),
            "metadata": self.metadata,
        }


def normalize_factor_name_v392(name: str) -> str:
    if name is None:
        raise ValueError("factor name cannot be None")
    value = str(name).strip().lower()
    value = _re_v392.sub(r"[\s\-/]+", "_", value)
    value = _re_v392.sub(r"[^a-z0-9_\.]+", "", value)
    value = _re_v392.sub(r"_+", "_", value)
    return value.strip("_")


def normalize_tag_v392(tag: str) -> str:
    if tag is None:
        raise ValueError("tag cannot be None")
    value = str(tag).strip().lower()
    value = _re_v392.sub(r"[\s\-/]+", "_", value)
    return value


def infer_family_v392(
    factor: BaseFactorV392,
    explicit_family: _OptV392["str | FactorFamilyV392"] = None,
) -> FactorFamilyV392:
    if explicit_family is not None:
        if isinstance(explicit_family, FactorFamilyV392):
            return explicit_family
        value = str(explicit_family).strip().lower()
        try:
            return FactorFamilyV392(value)
        except ValueError:
            raise ValueError(f"Unsupported factor family: {explicit_family}")
    name = normalize_factor_name_v392(getattr(factor, "name", ""))
    scope = getattr(getattr(factor, "config", None), "scope", None)
    if scope == FactorScopeV392.TECHNICAL:
        return FactorFamilyV392.TECHNICAL
    if scope == FactorScopeV392.FUNDAMENTAL:
        if any(
            x in name
            for x in [
                "pe", "pb", "ps", "price_to", "earnings_yield",
                "book_to_price", "sales_to_price", "value",
            ]
        ):
            return FactorFamilyV392.VALUE
        if any(
            x in name
            for x in [
                "roe", "roic", "roa", "quality", "margin", "asset_quality",
            ]
        ):
            return FactorFamilyV392.QUALITY
        if any(
            x in name
            for x in [
                "growth", "revenue_growth", "profit_growth", "earnings_growth",
            ]
        ):
            return FactorFamilyV392.GROWTH
        return FactorFamilyV392.FUNDAMENTAL
    if any(
        x in name
        for x in [
            "momentum", "reversal", "trend", "breakout", "ma_",
            "moving_average", "rsi",
        ]
    ):
        return FactorFamilyV392.MOMENTUM
    if any(
        x in name
        for x in ["volatility", "atr", "drawdown", "risk"]
    ):
        return FactorFamilyV392.RISK
    if any(
        x in name
        for x in ["turnover", "volume", "amount", "liquidity"]
    ):
        return FactorFamilyV392.LIQUIDITY
    return FactorFamilyV392.OTHER


class FactorRegistryV392:
    """全局因子注册中心 (V3.9.2)。"""

    def __init__(self) -> None:
        self._items: _DictV392[str, FactorDescriptorV392] = {}
        self._aliases: _DictV392[str, str] = {}

    def register(
        self,
        factor: BaseFactorV392,
        family: _OptV392["str | FactorFamilyV392"] = None,
        tags: _OptV392[_SeqV392[str]] = None,
        aliases: _OptV392[_SeqV392[str]] = None,
        metadata: _OptV392[_DictV392[str, _AnyV392]] = None,
        overwrite: bool = False,
    ) -> FactorDescriptorV392:
        if not isinstance(factor, BaseFactorV392):
            raise TypeError("factor must be an instance of BaseFactorV392")
        name = normalize_factor_name_v392(factor.name)
        if not name:
            raise ValueError("factor name cannot be empty")
        if name in self._items and not overwrite:
            raise FactorAlreadyExistsErrorV392(f"Factor already registered: {name}")
        if overwrite and name in self._items:
            old = self._items[name]
            for alias in old.aliases:
                if self._aliases.get(alias) == name:
                    del self._aliases[alias]
        config = getattr(factor, "config", None)
        version = str(
            getattr(
                config,
                "version",
                getattr(factor, "version", "1.0.0"),
            )
        )
        description = str(
            getattr(
                config,
                "description",
                factor.__class__.__name__,
            )
        )
        required_columns = list(getattr(config, "required_columns", []))
        scope = str(getattr(config, "scope", ""))
        direction = str(getattr(config, "direction", ""))
        lookback = getattr(config, "lookback", None)
        requires_pit = bool(getattr(config, "require_available_date", False))
        inferred_family = infer_family_v392(factor, explicit_family=family)
        tag_set = set()
        if tags:
            tag_set.update(normalize_tag_v392(x) for x in tags)
        tag_set.add(inferred_family.value)
        if scope:
            tag_set.add(normalize_tag_v392(scope))
        normalized_aliases = set()
        if aliases:
            normalized_aliases.update(normalize_factor_name_v392(x) for x in aliases)
        original_name = normalize_factor_name_v392(factor.name)
        if original_name != name:
            normalized_aliases.add(original_name)
        normalized_aliases.discard(name)
        for alias in normalized_aliases:
            existing = self._aliases.get(alias)
            if existing is not None and existing != name:
                raise FactorAliasConflictErrorV392(
                    f"Alias '{alias}' already belongs to factor '{existing}'"
                )
            if alias in self._items and alias != name:
                raise FactorAliasConflictErrorV392(
                    f"Alias '{alias}' conflicts with factor name '{alias}'"
                )
        merged_metadata: _DictV392[str, _AnyV392] = {}
        factor_metadata = getattr(config, "metadata", None)
        if isinstance(factor_metadata, dict):
            merged_metadata.update(factor_metadata)
        if metadata:
            merged_metadata.update(metadata)
        descriptor = FactorDescriptorV392(
            name=name,
            family=inferred_family,
            version=version,
            description=description,
            factor=factor,
            tags=sorted(tag_set),
            aliases=sorted(normalized_aliases),
            scope=scope,
            direction=direction,
            lookback=lookback,
            requires_pit=requires_pit,
            required_columns=required_columns,
            metadata=merged_metadata,
        )
        self._items[name] = descriptor
        for alias in descriptor.aliases:
            self._aliases[alias] = name
        _logger_v392.debug("Registered factor: %s", name)
        return descriptor

    def register_many(
        self,
        factors: _IterableV392[BaseFactorV392],
        family: _OptV392["str | FactorFamilyV392"] = None,
        tags: _OptV392[_SeqV392[str]] = None,
        overwrite: bool = False,
    ) -> _ListV392[FactorDescriptorV392]:
        results = []
        for factor in factors:
            results.append(
                self.register(
                    factor=factor,
                    family=family,
                    tags=tags,
                    overwrite=overwrite,
                )
            )
        return results

    def unregister(self, name: str) -> FactorDescriptorV392:
        canonical = self.resolve_name(name)
        if canonical not in self._items:
            raise FactorNotFoundErrorV392(f"Factor not found: {name}")
        descriptor = self._items.pop(canonical)
        for alias in descriptor.aliases:
            if self._aliases.get(alias) == canonical:
                del self._aliases[alias]
        return descriptor

    def resolve_name(self, name: str) -> str:
        normalized = normalize_factor_name_v392(name)
        if normalized in self._items:
            return normalized
        if normalized in self._aliases:
            return self._aliases[normalized]
        raise FactorNotFoundErrorV392(f"Factor not found: {name}")

    def contains(self, name: str) -> bool:
        try:
            self.resolve_name(name)
            return True
        except FactorNotFoundErrorV392:
            return False

    def descriptor(self, name: str) -> FactorDescriptorV392:
        canonical = self.resolve_name(name)
        return self._items[canonical]

    def get(self, name: str) -> BaseFactorV392:
        return self.descriptor(name).factor

    def list_names(self, include_aliases: bool = False) -> _ListV392[str]:
        names = sorted(self._items.keys())
        if not include_aliases:
            return names
        return sorted(set(names) | set(self._aliases.keys()))

    def list_descriptors(self) -> _ListV392[FactorDescriptorV392]:
        return [self._items[name] for name in sorted(self._items.keys())]

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, name: str) -> bool:
        return self.contains(name)

    def by_family(
        self, family: "str | FactorFamilyV392"
    ) -> _ListV392[FactorDescriptorV392]:
        if isinstance(family, FactorFamilyV392):
            target = family
        else:
            target = FactorFamilyV392(str(family).lower())
        return [
            item
            for item in self.list_descriptors()
            if item.family == target
        ]

    def by_tag(self, tag: str) -> _ListV392[FactorDescriptorV392]:
        target = normalize_tag_v392(tag)
        return [
            item
            for item in self.list_descriptors()
            if target in item.tags
        ]

    def by_scope(
        self, scope: "str | FactorScopeV392"
    ) -> _ListV392[FactorDescriptorV392]:
        if isinstance(scope, FactorScopeV392):
            target = str(scope)
        else:
            target = str(scope)
        return [
            item
            for item in self.list_descriptors()
            if str(item.scope) == target
            or str(item.scope).lower() == target.lower()
        ]

    def pit_required(self) -> _ListV392[FactorDescriptorV392]:
        return [
            item for item in self.list_descriptors() if item.requires_pit
        ]

    def search(
        self,
        query: str = "",
        family: _OptV392["str | FactorFamilyV392"] = None,
        tag: _OptV392[str] = None,
        requires_pit: _OptV392[bool] = None,
    ) -> _ListV392[FactorDescriptorV392]:
        query_normalized = normalize_factor_name_v392(query) if query else ""
        candidates = self.list_descriptors()
        if family is not None:
            target_family = (
                family
                if isinstance(family, FactorFamilyV392)
                else FactorFamilyV392(str(family).lower())
            )
            candidates = [
                item for item in candidates if item.family == target_family
            ]
        if tag is not None:
            target_tag = normalize_tag_v392(tag)
            candidates = [
                item for item in candidates if target_tag in item.tags
            ]
        if requires_pit is not None:
            candidates = [
                item
                for item in candidates
                if item.requires_pit == requires_pit
            ]
        if query_normalized:
            results = []
            for item in candidates:
                haystack = " ".join(
                    [
                        item.name,
                        item.description,
                        item.family.value,
                        " ".join(item.tags),
                        " ".join(item.aliases),
                    ]
                ).lower()
                if query_normalized in haystack:
                    results.append(item)
            candidates = results
        return candidates

    def metadata(self, name: str) -> _DictV392[str, _AnyV392]:
        return self.descriptor(name).public_metadata()

    def all_metadata(self) -> _ListV392[_DictV392[str, _AnyV392]]:
        return [item.public_metadata() for item in self.list_descriptors()]

    def snapshot(self) -> _DictV392[str, _AnyV392]:
        return {
            "factor_count": len(self),
            "alias_count": len(self._aliases),
            "factors": self.all_metadata(),
        }

    def snapshot_hash(self) -> str:
        payload = _json_v392.dumps(
            self.snapshot(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return _hashlib_v392.sha256(payload.encode("utf-8")).hexdigest()

    def export_json(self, path: "str | _PathV392") -> _PathV392:
        output = _PathV392(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = self.snapshot()
        payload["snapshot_hash"] = self.snapshot_hash()
        with output.open("w", encoding="utf-8") as f:
            _json_v392.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        return output

    def summary(self) -> _DictV392[str, _AnyV392]:
        family_counts: _DictV392[str, int] = {}
        for item in self.list_descriptors():
            key = item.family.value
            family_counts[key] = family_counts.get(key, 0) + 1
        return {
            "factor_count": len(self),
            "alias_count": len(self._aliases),
            "family_counts": dict(sorted(family_counts.items())),
            "pit_required_count": len(self.pit_required()),
            "snapshot_hash": self.snapshot_hash(),
        }


def build_default_registry_v392(
    include_technical: bool = True,
    include_fundamental: bool = True,
    strict_pit: bool = True,
) -> FactorRegistryV392:
    registry = FactorRegistryV392()
    if include_technical:
        from .technical import build_default_technical_factors_v392
        for factor in build_default_technical_factors_v392():
            registry.register(
                factor=factor,
                tags=["technical", "market"],
            )
    if include_fundamental:
        from .fundamental import build_default_fundamental_factors_v392
        for factor in build_default_fundamental_factors_v392(strict_pit=strict_pit):
            registry.register(
                factor=factor,
                tags=["fundamental", "pit"] if strict_pit else ["fundamental"],
            )
    return registry


DEFAULT_REGISTRY_V392 = FactorRegistryV392()


def get_default_registry_v392() -> FactorRegistryV392:
    return DEFAULT_REGISTRY_V392


def register_factor_v392(
    factor: BaseFactorV392,
    family: _OptV392["str | FactorFamilyV392"] = None,
    tags: _OptV392[_SeqV392[str]] = None,
    aliases: _OptV392[_SeqV392[str]] = None,
    metadata: _OptV392[_DictV392[str, _AnyV392]] = None,
    overwrite: bool = False,
) -> FactorDescriptorV392:
    return DEFAULT_REGISTRY_V392.register(
        factor=factor,
        family=family,
        tags=tags,
        aliases=aliases,
        metadata=metadata,
        overwrite=overwrite,
    )


def get_factor_v392(name: str) -> BaseFactorV392:
    return DEFAULT_REGISTRY_V392.get(name)


def list_factors_v392() -> _ListV392[str]:
    return DEFAULT_REGISTRY_V392.list_names()


def find_factors_v392(
    query: str = "",
    family: _OptV392["str | FactorFamilyV392"] = None,
    tag: _OptV392[str] = None,
    requires_pit: _OptV392[bool] = None,
) -> _ListV392[FactorDescriptorV392]:
    return DEFAULT_REGISTRY_V392.search(
        query=query,
        family=family,
        tag=tag,
        requires_pit=requires_pit,
    )


def run_self_test_v392() -> _DictV392[str, _AnyV392]:
    import pandas as _pd_v392
    import tempfile as _tempfile_v392

    registry = FactorRegistryV392()

    class TestFactorV392(BaseFactorV392):
        def __init__(
            self,
            name: str,
            version: str = "1.0.0",
            scope: FactorScopeV392 = FactorScopeV392.CROSS_SECTIONAL,
            require_pit: bool = False,
        ):
            config = FactorConfigV392(
                name=name,
                version=version,
                description=f"Test factor: {name}",
                required_columns=["date", "code", "close"],
                output_column=name,
                scope=scope,
                direction=FactorDirectionV392.POSITIVE,
                lookback=20,
                require_available_date=require_pit,
                metadata={"test": True},
            )
            super().__init__(config)

        def compute(self, df, context=None):
            return df["close"].astype(float)

    momentum = TestFactorV392(
        name="momentum_20",
        scope=FactorScopeV392.TECHNICAL,
    )
    registry.register(
        momentum,
        family=FactorFamilyV392.MOMENTUM,
        tags=["technical", "trend"],
        aliases=["mom20", "momentum20"],
    )
    assert registry.contains("momentum_20")
    assert registry.contains("mom20")
    assert registry.resolve_name("mom20") == "momentum_20"
    assert registry.get("momentum_20") is momentum

    momentum_results = registry.by_family(FactorFamilyV392.MOMENTUM)
    assert len(momentum_results) == 1

    technical_results = registry.by_tag("technical")
    assert len(technical_results) == 1

    roe = TestFactorV392(
        name="roe",
        scope=FactorScopeV392.FUNDAMENTAL,
        require_pit=True,
    )
    registry.register(
        roe,
        family=FactorFamilyV392.QUALITY,
        tags=["fundamental", "quality", "pit"],
    )
    assert registry.contains("roe")
    pit_factors = registry.pit_required()
    assert len(pit_factors) == 1

    results = registry.search(query="momentum")
    assert len(results) == 1
    results = registry.search(family=FactorFamilyV392.QUALITY)
    assert len(results) == 1
    results = registry.search(requires_pit=True)
    assert len(results) == 1

    duplicate_error = False
    try:
        registry.register(momentum)
    except FactorAlreadyExistsErrorV392:
        duplicate_error = True
    assert duplicate_error

    snapshot = registry.snapshot()
    assert snapshot["factor_count"] == 2
    assert snapshot["alias_count"] == 2
    snapshot_hash = registry.snapshot_hash()
    assert isinstance(snapshot_hash, str)
    assert len(snapshot_hash) == 64

    with _tempfile_v392.TemporaryDirectory() as tmp:
        output = registry.export_json(_PathV392(tmp) / "registry.json")
        assert output.exists()
        loaded = _json_v392.loads(output.read_text(encoding="utf-8"))
        assert loaded["factor_count"] == 2
        assert "snapshot_hash" in loaded

    removed = registry.unregister("mom20")
    assert removed.name == "momentum_20"
    assert not registry.contains("momentum_20")

    return {
        "status": "ok",
        "factor_count_before_remove": 2,
        "factor_count_after_remove": len(registry),
        "snapshot_hash": snapshot_hash,
    }


if __name__ == "__main__":
    _logging_v392.basicConfig(level=_logging_v392.INFO)
    result = run_self_test_v392()
    print(_json_v392.dumps(result, ensure_ascii=False, indent=2))
