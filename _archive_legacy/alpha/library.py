from __future__ import annotations

import json
from pathlib import Path


class AlphaLibrary:
    def __init__(self, path="alpha_library.json"):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return []
        return json.loads(
            self.path.read_text(encoding="utf-8")
        )

    def save(self, alpha):
        library = self.load()
        library.append(alpha)
        self.path.write_text(
            json.dumps(
                library,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def top(self, n=20):
        library = self.load()
        library.sort(
            key=lambda x: x.get(
                "oos_score",
                x.get("adjusted_score", 0),
            ),
            reverse=True,
        )
        return library[:n]
# ============================================================================
# V3.9.1 unified research engine - alpha library (directory based, dump)
# ============================================================================


class AlphaLibraryV391:
    def __init__(self, root=Path("alpha_library")):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "alphas.json"

    def save(self, records: list[dict]):
        serializable = []
        for record in records:
            item = {}
            for key, value in record.items():
                if key in {"expression", "signal", "ic_series"}:
                    continue
                item[key] = value
            if "expression" in record:
                item["expression"] = record["expression"].to_string()
            serializable.append(item)
        self.path.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def load(self):
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def top(self, n: int = 20):
        return self.load()[:n]



import hashlib  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
from dataclasses import asdict, dataclass, field  # noqa: E402
from datetime import date, datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Dict, Iterable, List, Optional, Sequence  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from alpha.expression import AlphaExpression  # noqa: E402

logger = logging.getLogger(__name__)

# ============================================================================
# V3.9.2 - Alpha Library (appended, V392 suffix)
# ============================================================================

class AlphaLibraryErrorV392(Exception):
    """Alpha Library 基础异常。"""


class AlphaAlreadyExistsErrorV392(AlphaLibraryErrorV392):
    """Alpha 已存在。"""


class AlphaNotFoundErrorV392(AlphaLibraryErrorV392):
    """Alpha 不存在。"""


class AlphaSerializationErrorV392(AlphaLibraryErrorV392):
    """Alpha 序列化失败。"""


class AlphaValidationStateErrorV392(AlphaLibraryErrorV392):
    """Alpha 状态更新非法。"""


def _json_safe_v392(value: Any) -> Any:
    """将 numpy / pandas / datetime 等对象转换成 JSON 可序列化对象。"""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return _json_safe_v392(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.Series):
        return [_json_safe_v392(v) for v in value.tolist()]
    if isinstance(value, pd.Index):
        return [_json_safe_v392(v) for v in value.tolist()]
    if isinstance(value, np.ndarray):
        return [_json_safe_v392(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): _json_safe_v392(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_v392(v) for v in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def expression_to_dict_v392(expression: AlphaExpression) -> Dict[str, Any]:
    """将 AlphaExpression 递归序列化为 dict。"""
    if expression is None:
        raise AlphaSerializationErrorV392("expression cannot be None")
    children = getattr(expression, "children", None)
    if children is None:
        children = []
    return {
        "operator": getattr(expression, "operator", None),
        "value": _json_safe_v392(getattr(expression, "value", None)),
        "feature": getattr(expression, "feature", None),
        "children": [expression_to_dict_v392(child) for child in children],
    }


def expression_from_dict_v392(payload: Dict[str, Any]) -> AlphaExpression:
    """从 dict 递归恢复 AlphaExpression。"""
    if not isinstance(payload, dict):
        raise AlphaSerializationErrorV392("Expression payload must be a dict.")
    operator = payload.get("operator")
    if not operator:
        raise AlphaSerializationErrorV392("Expression payload missing operator.")
    children_payload = payload.get("children", [])
    children = [expression_from_dict_v392(child) for child in children_payload]
    return AlphaExpression(
        operator=operator,
        children=children,
        value=payload.get("value"),
        feature=payload.get("feature"),
    )


def expression_to_string_v392(expression: AlphaExpression) -> str:
    """将 Expression 转换为可读字符串。"""
    if expression is None:
        return "None"
    operator = str(getattr(expression, "operator", "")).lower()
    feature = getattr(expression, "feature", None)
    value = getattr(expression, "value", None)
    children = getattr(expression, "children", []) or []

    if operator in {"feature", "input"}:
        return str(feature)
    if operator in {"constant", "const", "value"}:
        return str(value)
    child_strings = [expression_to_string_v392(child) for child in children]

    if operator == "neg":
        return f"(-{child_strings[0]})"
    if operator == "abs":
        return f"abs({child_strings[0]})"
    if operator == "log":
        return f"log({child_strings[0]})"
    if operator == "rank":
        return f"rank({child_strings[0]})"
    if operator == "zscore":
        return f"zscore({child_strings[0]})"
    if operator == "add":
        return "(" + " + ".join(child_strings) + ")"
    if operator == "sub":
        return "(" + " - ".join(child_strings) + ")"
    if operator == "mul":
        return "(" + " * ".join(child_strings) + ")"
    if operator == "div":
        return "(" + " / ".join(child_strings) + ")"
    return f"{operator}({', '.join(child_strings)})"


def infer_alpha_direction_v392(
    metrics: Optional[Dict[str, Any]] = None,
) -> str:
    """根据 signed IC 推断方向。绝不使用 abs(IC)。"""
    metrics = metrics or {}
    ic = metrics.get("ic_mean")
    try:
        ic = float(ic)
    except (TypeError, ValueError):
        return "neutral"
    if not np.isfinite(ic):
        return "neutral"
    if ic > 0:
        return "positive"
    if ic < 0:
        return "negative"
    return "neutral"


@dataclass
class AlphaRecordV392:
    """
    Alpha Library 中的标准记录。
    status 生命周期：candidate -> validated -> active -> retired
    如果 OOS 未通过：candidate -> rejected
    """
    alpha_id: str
    expression: Dict[str, Any]
    expression_string: str
    direction: str = "neutral"
    metrics: Dict[str, Any] = field(default_factory=dict)
    complexity: Dict[str, Any] = field(default_factory=dict)
    status: str = "candidate"
    train_period: Optional[Dict[str, Any]] = None
    validation_period: Optional[Dict[str, Any]] = None
    oos_period: Optional[Dict[str, Any]] = None
    data_version: Optional[str] = None
    factor_versions: Dict[str, Any] = field(default_factory=dict)
    experiment_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    schema_version: str = "3.9.2"

    def to_expression(self) -> AlphaExpression:
        return expression_from_dict_v392(self.expression)

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe_v392(asdict(self))

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AlphaRecordV392":
        allowed_fields = {
            field_name for field_name in cls.__dataclass_fields__
        }
        cleaned = {
            key: value
            for key, value in payload.items()
            if key in allowed_fields
        }
        return cls(**cleaned)

    @classmethod
    def from_candidate(
        cls,
        candidate: Any,
        *,
        status: str = "candidate",
        train_period: Optional[Dict[str, Any]] = None,
        validation_period: Optional[Dict[str, Any]] = None,
        oos_period: Optional[Dict[str, Any]] = None,
        data_version: Optional[str] = None,
        factor_versions: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AlphaRecordV392":
        expression = getattr(candidate, "expression", None)
        if expression is None:
            raise AlphaSerializationErrorV392(
                "AlphaCandidate does not contain expression."
            )
        alpha_id = str(
            getattr(candidate, "alpha_id", "")
            or getattr(candidate, "id", "")
        )
        if not alpha_id:
            raise AlphaSerializationErrorV392(
                "AlphaCandidate does not contain alpha_id."
            )
        metrics = getattr(candidate, "metrics", {}) or {}
        complexity = getattr(candidate, "complexity", {}) or {}
        direction = getattr(candidate, "direction", None)
        if direction is None:
            direction = infer_alpha_direction_v392(metrics)
        candidate_metadata = getattr(candidate, "metadata", {}) or {}
        merged_metadata = dict(candidate_metadata)
        if metadata:
            merged_metadata.update(metadata)

        return cls(
            alpha_id=alpha_id,
            expression=expression_to_dict_v392(expression),
            expression_string=expression_to_string_v392(expression),
            direction=str(direction),
            metrics=_json_safe_v392(metrics),
            complexity=_json_safe_v392(complexity),
            status=status,
            train_period=_json_safe_v392(train_period),
            validation_period=_json_safe_v392(validation_period),
            oos_period=_json_safe_v392(oos_period),
            data_version=data_version,
            factor_versions=_json_safe_v392(factor_versions or {}),
            experiment_id=experiment_id,
            tags=sorted(
                set(str(x) for x in (tags or []))
            ),
            metadata=_json_safe_v392(merged_metadata),
        )


@dataclass
class AlphaLibraryConfigV392:
    path: str = "data/alpha_library.json"
    schema_version: str = "3.9.2"
    overwrite: bool = False
    max_size: Optional[int] = None
    auto_save: bool = True
    allowed_statuses: Sequence[str] = field(
        default_factory=lambda: (
            "candidate",
            "validated",
            "active",
            "retired",
            "rejected",
        )
    )


class AlphaLibraryV392:
    """
    Alpha Library。
    Search Engine -> AlphaCandidate -> AlphaLibrary -> OOS Validation -> validated -> active
    """

    def __init__(
        self,
        config: Optional[AlphaLibraryConfigV392] = None,
    ):
        self.config = config or AlphaLibraryConfigV392()
        self.path = Path(self.config.path)
        self._records: Dict[str, AlphaRecordV392] = {}
        self.load()

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, alpha_id: str) -> bool:
        return str(alpha_id) in self._records

    def contains(self, alpha_id: str) -> bool:
        return str(alpha_id) in self._records

    def add(
        self,
        record: AlphaRecordV392,
        *,
        overwrite: Optional[bool] = None,
    ) -> AlphaRecordV392:
        alpha_id = str(record.alpha_id)
        if not alpha_id:
            raise AlphaLibraryErrorV392("alpha_id cannot be empty.")
        allowed_statuses = set(self.config.allowed_statuses)
        if record.status not in allowed_statuses:
            raise AlphaValidationStateErrorV392(
                f"Unsupported alpha status: {record.status}"
            )
        exists = alpha_id in self._records
        should_overwrite = (
            self.config.overwrite if overwrite is None else overwrite
        )
        if exists and not should_overwrite:
            raise AlphaAlreadyExistsErrorV392(
                f"Alpha already exists: {alpha_id}"
            )
        now = datetime.utcnow().isoformat()
        if exists:
            record.created_at = self._records[alpha_id].created_at
        record.updated_at = now
        self._records[alpha_id] = record
        self._enforce_max_size()
        if self.config.auto_save:
            self.save()
        return record

    def add_candidate(
        self,
        candidate: Any,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Sequence[str]] = None,
        save: Optional[bool] = None,
    ) -> AlphaRecordV392:
        record = AlphaRecordV392.from_candidate(
            candidate,
            status="candidate",
            metadata=metadata,
            tags=tags,
        )
        old_auto_save = self.config.auto_save
        if save is not None:
            self.config.auto_save = save
        try:
            return self.add(record, overwrite=True)
        finally:
            self.config.auto_save = old_auto_save

    def add_candidates(
        self,
        candidates: Iterable[Any],
        *,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> List[AlphaRecordV392]:
        records = []
        for candidate in candidates:
            record = self.add_candidate(
                candidate,
                metadata=metadata,
                tags=tags,
            )
            records.append(record)
        return records

    def get(self, alpha_id: str) -> AlphaRecordV392:
        alpha_id = str(alpha_id)
        if alpha_id not in self._records:
            raise AlphaNotFoundErrorV392(
                f"Alpha not found: {alpha_id}"
            )
        return self._records[alpha_id]

    def get_or_none(self, alpha_id: str) -> Optional[AlphaRecordV392]:
        return self._records.get(str(alpha_id))

    def remove(
        self,
        alpha_id: str,
        *,
        save: Optional[bool] = None,
    ) -> AlphaRecordV392:
        alpha_id = str(alpha_id)
        record = self.get(alpha_id)
        del self._records[alpha_id]
        should_save = (
            self.config.auto_save if save is None else save
        )
        if should_save:
            self.save()
        return record

    def update_status(
        self,
        alpha_id: str,
        status: str,
        *,
        reason: Optional[str] = None,
        save: Optional[bool] = None,
    ) -> AlphaRecordV392:
        allowed = set(self.config.allowed_statuses)
        if status not in allowed:
            raise AlphaValidationStateErrorV392(
                f"Unsupported status: {status}"
            )
        record = self.get(alpha_id)
        old_status = record.status
        record.status = status
        record.updated_at = datetime.utcnow().isoformat()
        if reason:
            record.metadata["status_change_reason"] = reason
        record.metadata["previous_status"] = old_status
        should_save = (
            self.config.auto_save if save is None else save
        )
        if should_save:
            self.save()
        return record

    def update_validation(
        self,
        alpha_id: str,
        *,
        passed: bool,
        oos_metrics: Optional[Dict[str, Any]] = None,
        oos_period: Optional[Dict[str, Any]] = None,
        validation_period: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        save: Optional[bool] = None,
    ) -> AlphaRecordV392:
        record = self.get(alpha_id)
        oos_metrics = oos_metrics or {}
        record.validation = {
            "passed": bool(passed),
            "oos_metrics": _json_safe_v392(oos_metrics),
            "validated_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "metadata": _json_safe_v392(metadata or {}),
        }
        if oos_period is not None:
            record.oos_period = _json_safe_v392(oos_period)
        if validation_period is not None:
            record.validation_period = _json_safe_v392(validation_period)
        if passed:
            record.status = "validated"
        else:
            record.status = "rejected"
        record.updated_at = datetime.utcnow().isoformat()
        should_save = (
            self.config.auto_save if save is None else save
        )
        if should_save:
            self.save()
        return record

    def activate(
        self,
        alpha_id: str,
        *,
        reason: Optional[str] = None,
        save: Optional[bool] = None,
    ) -> AlphaRecordV392:
        record = self.get(alpha_id)
        if record.status != "validated":
            raise AlphaValidationStateErrorV392(
                "Only validated Alpha can be activated. "
                f"Current status={record.status}"
            )
        return self.update_status(
            alpha_id,
            "active",
            reason=reason,
            save=save,
        )

    def retire(
        self,
        alpha_id: str,
        *,
        reason: Optional[str] = None,
        save: Optional[bool] = None,
    ) -> AlphaRecordV392:
        return self.update_status(
            alpha_id,
            "retired",
            reason=reason,
            save=save,
        )

    def list_records(
        self,
        *,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        sort_by: str = "score",
        descending: bool = True,
    ) -> List[AlphaRecordV392]:
        records = list(self._records.values())
        if status is not None:
            records = [
                r for r in records if r.status == status
            ]
        if direction is not None:
            records = [
                r for r in records if r.direction == direction
            ]
        if tags:
            wanted_tags = set(str(x) for x in tags)
            records = [
                r
                for r in records
                if wanted_tags.intersection(set(r.tags))
            ]

        def sort_key(record: AlphaRecordV392) -> float:
            if sort_by == "score":
                value = record.metrics.get("score")
            elif sort_by == "ic_mean":
                value = record.metrics.get("ic_mean")
            elif sort_by == "icir":
                value = record.metrics.get("icir")
            elif sort_by == "spread":
                value = record.metrics.get("high_low_spread")
            elif sort_by == "turnover":
                value = record.metrics.get("turnover")
            elif sort_by == "created_at":
                value = record.created_at
            else:
                value = record.metrics.get(sort_by)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    return 0.0
            try:
                value = float(value)
            except (TypeError, ValueError):
                return 0.0
            if not np.isfinite(value):
                return 0.0
            return value

        records.sort(key=sort_key, reverse=descending)
        if limit is not None:
            records = records[: max(0, int(limit))]
        return records

    def search(
        self,
        *,
        min_ic: Optional[float] = None,
        min_icir: Optional[float] = None,
        min_spread: Optional[float] = None,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AlphaRecordV392]:
        records = self.list_records(
            status=status,
            direction=direction,
        )
        result = []
        query_lower = query.lower() if query else None
        for record in records:
            ic = record.metrics.get("ic_mean")
            icir = record.metrics.get("icir")
            spread = record.metrics.get("high_low_spread")
            try:
                ic = float(ic)
            except (TypeError, ValueError):
                ic = np.nan
            try:
                icir = float(icir)
            except (TypeError, ValueError):
                icir = np.nan
            try:
                spread = float(spread)
            except (TypeError, ValueError):
                spread = np.nan
            if min_ic is not None:
                if not np.isfinite(ic) or abs(ic) < min_ic:
                    continue
            if min_icir is not None:
                if not np.isfinite(icir) or abs(icir) < min_icir:
                    continue
            if min_spread is not None:
                if not np.isfinite(spread) or abs(spread) < min_spread:
                    continue
            if query_lower:
                text = " ".join([
                    record.alpha_id,
                    record.expression_string,
                    " ".join(record.tags),
                    json.dumps(
                        record.metadata,
                        ensure_ascii=False,
                        default=str,
                    ),
                ]).lower()
                if query_lower not in text:
                    continue
            result.append(record)
        if limit is not None:
            result = result[: max(0, int(limit))]
        return result

    def top(
        self,
        n: int = 20,
        *,
        status: Optional[str] = None,
        sort_by: str = "score",
    ) -> List[AlphaRecordV392]:
        return self.list_records(
            status=status,
            limit=n,
            sort_by=sort_by,
            descending=True,
        )

    def to_frame(
        self,
        *,
        status: Optional[str] = None,
    ) -> pd.DataFrame:
        records = self.list_records(status=status)
        rows = []
        for record in records:
            row = {
                "alpha_id": record.alpha_id,
                "expression": record.expression_string,
                "direction": record.direction,
                "status": record.status,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "data_version": record.data_version,
                "experiment_id": record.experiment_id,
            }
            row.update({
                f"metric_{k}": v
                for k, v in record.metrics.items()
            })
            row.update({
                f"complexity_{k}": v
                for k, v in record.complexity.items()
            })
            rows.append(row)
        if not rows:
            return pd.DataFrame(
                columns=[
                    "alpha_id",
                    "expression",
                    "direction",
                    "status",
                    "created_at",
                    "updated_at",
                ]
            )
        return pd.DataFrame(rows)

    def save(self, path: Optional[str] = None) -> Path:
        target = Path(
            path if path is not None else self.path
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.config.schema_version,
            "updated_at": datetime.utcnow().isoformat(),
            "count": len(self._records),
            "records": [
                record.to_dict()
                for record in self._records.values()
            ],
        }
        payload = _json_safe_v392(payload)

        fd, temp_name = tempfile.mkstemp(
            prefix=".alpha_library_",
            suffix=".tmp",
            dir=str(target.parent),
        )
        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    payload,
                    f,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=False,
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        return target

    def load(self, path: Optional[str] = None) -> int:
        target = Path(
            path if path is not None else self.path
        )
        if not target.exists():
            return 0
        with target.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        records_payload = payload.get("records", [])
        self._records = {}
        for item in records_payload:
            try:
                record = AlphaRecordV392.from_dict(item)
                self._records[record.alpha_id] = record
            except Exception as exc:
                logger.warning(
                    "Failed to load Alpha record: %s",
                    exc,
                )
        return len(self._records)

    def export_json(self, path: str) -> Path:
        return self.save(path=path)

    def snapshot(self) -> Dict[str, Any]:
        records = [
            record.to_dict()
            for record in sorted(
                self._records.values(),
                key=lambda x: x.alpha_id,
            )
        ]
        return {
            "schema_version": self.config.schema_version,
            "count": len(records),
            "records": records,
        }

    def snapshot_hash(self) -> str:
        payload = json.dumps(
            self.snapshot(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def stats(self) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        direction_counts: Dict[str, int] = {}
        for record in self._records.values():
            status_counts[record.status] = (
                status_counts.get(record.status, 0) + 1
            )
            direction_counts[record.direction] = (
                direction_counts.get(record.direction, 0) + 1
            )
        return {
            "count": len(self._records),
            "status_counts": status_counts,
            "direction_counts": direction_counts,
            "snapshot_hash": self.snapshot_hash(),
        }

    def _enforce_max_size(self) -> None:
        max_size = self.config.max_size
        if max_size is None:
            return
        max_size = int(max_size)
        if max_size <= 0:
            self._records.clear()
            return
        if len(self._records) <= max_size:
            return
        priority = {
            "rejected": 0,
            "retired": 1,
            "candidate": 2,
            "validated": 3,
            "active": 4,
        }
        records = sorted(
            self._records.values(),
            key=lambda r: (
                priority.get(r.status, 0),
                r.created_at,
            ),
        )
        remove_count = (
            len(records) - max_size
        )
        for record in records[:remove_count]:
            self._records.pop(record.alpha_id, None)

    def clear(
        self,
        *,
        status: Optional[str] = None,
        save: Optional[bool] = None,
    ) -> int:
        if status is None:
            count = len(self._records)
            self._records.clear()
        else:
            ids = [
                alpha_id
                for alpha_id, record in self._records.items()
                if record.status == status
            ]
            for alpha_id in ids:
                del self._records[alpha_id]
            count = len(ids)
        should_save = (
            self.config.auto_save if save is None else save
        )
        if should_save:
            self.save()
        return count

    def summary(self) -> Dict[str, Any]:
        frame = self.to_frame()
        result = self.stats()
        if frame.empty:
            result.update({
                "mean_ic": None,
                "mean_icir": None,
                "mean_spread": None,
            })
            return result
        for column, key in [
            ("metric_ic_mean", "mean_ic"),
            ("metric_icir", "mean_icir"),
            ("metric_high_low_spread", "mean_spread"),
        ]:
            if column in frame.columns:
                values = pd.to_numeric(
                    frame[column],
                    errors="coerce",
                )
                result[key] = (
                    float(values.mean())
                    if values.notna().any()
                    else None
                )
            else:
                result[key] = None
        return result


def save_alpha_library_v392(
    records: Iterable[AlphaRecordV392],
    path: str = "data/alpha_library.json",
) -> Path:
    library = AlphaLibraryV392(
        AlphaLibraryConfigV392(
            path=path,
            auto_save=False,
        )
    )
    for record in records:
        library.add(record, overwrite=True)
    return library.save()


def load_alpha_library_v392(
    path: str = "data/alpha_library.json",
) -> AlphaLibraryV392:
    return AlphaLibraryV392(
        AlphaLibraryConfigV392(
            path=path
        )
    )


def _self_test_v392() -> None:
    import tempfile

    expression = AlphaExpression(
        operator="add",
        children=[
            AlphaExpression(
                operator="feature",
                feature="roe",
            ),
            AlphaExpression(
                operator="feature",
                feature="momentum_20",
            ),
        ],
    )
    expression_dict = expression_to_dict_v392(expression)
    restored = expression_from_dict_v392(expression_dict)
    assert expression_to_string_v392(expression) == "(roe + momentum_20)"
    assert expression_to_string_v392(restored) == "(roe + momentum_20)"

    class FakeCandidate:
        def __init__(self):
            self.alpha_id = "alpha_test_001"
            self.expression = expression
            self.metrics = {
                "ic_mean": 0.045,
                "icir": 1.35,
                "high_low_spread": 0.018,
                "turnover": 0.22,
                "score": 0.061,
            }
            self.complexity = {
                "nodes": 3,
                "depth": 2,
                "penalty": 0.001,
            }
            self.direction = "positive"
            self.metadata = {
                "generator": "random",
                "seed": 42,
            }

    candidate = FakeCandidate()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "alpha_library.json"
        config = AlphaLibraryConfigV392(
            path=str(path),
            auto_save=True,
        )
        library = AlphaLibraryV392(config)

        record = library.add_candidate(
            candidate,
            tags=["quality", "momentum"],
            metadata={"test": True},
        )
        assert record.alpha_id == "alpha_test_001"
        assert record.status == "candidate"
        assert len(library) == 1

        library2 = AlphaLibraryV392(
            AlphaLibraryConfigV392(
                path=str(path),
                auto_save=False,
            )
        )
        assert len(library2) == 1
        loaded = library2.get("alpha_test_001")
        assert loaded.expression_string == "(roe + momentum_20)"
        restored_expression = loaded.to_expression()
        assert (
            expression_to_string_v392(restored_expression)
            == "(roe + momentum_20)"
        )

        result = library2.search(min_ic=0.03)
        assert len(result) == 1

        updated = library2.update_validation(
            "alpha_test_001",
            passed=True,
            oos_metrics={
                "ic_mean": 0.031,
                "icir": 0.82,
            },
            oos_period={
                "start": "2025-01-01",
                "end": "2025-06-30",
            },
            reason="OOS passed threshold.",
        )
        assert updated.status == "validated"

        active = library2.activate("alpha_test_001")
        assert active.status == "active"

        stats = library2.stats()
        assert stats["count"] == 1
        assert stats["status_counts"]["active"] == 1

        frame = library2.to_frame()
        assert len(frame) == 1
        assert "metric_ic_mean" in frame.columns

        hash1 = library2.snapshot_hash()
        hash2 = library2.snapshot_hash()
        assert hash1 == hash2

    print("alpha/library.py self-test passed.")


if __name__ == "__main__":
    _self_test_v392()
