"""V3.9.2 - Experiment Registry (V392 suffix names)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import uuid
from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import (
    Any,
    Iterable,
    Optional,
)


# ============================================================
# Helpers
# ============================================================
def utc_now_iso_v392() -> str:
    """
    返回 UTC ISO 时间。
    """
    return (
        datetime.now(
            timezone.utc
        ).replace(
            microsecond=0
        ).isoformat()
    )


def make_experiment_id_v392(
    prefix: str = "exp",
) -> str:
    """
    创建实验 ID。

    Example:

        exp_20260904_abc12345
    """
    now = datetime.now(
        timezone.utc
    )
    random_part = uuid.uuid4().hex[:8]
    return (
        f"{prefix}_"
        f"{now.strftime('%Y%m%d_%H%M%S')}_"
        f"{random_part}"
    )


def stable_hash_v392(
    value: Any,
) -> str:
    """
    对对象生成稳定 SHA256。

    用于：

    - 参数指纹
    - Alpha 指纹
    - 实验配置指纹
    """
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(
            ",",
            ":",
        ),
    )
    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def safe_float_v392(
    value: Any,
) -> Optional[float]:
    """
    将数值安全转换为 float。
    """
    if value is None:
        return None
    try:
        result = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None
    if result != result:
        return None
    if result in (
        float("inf"),
        float("-inf"),
    ):
        return None
    return result


# ============================================================
# Experiment Status
# ============================================================
class ExperimentStatusV392:
    """
    实验状态常量。

    使用字符串而不是 Enum，
    保证 JSON 序列化简单。
    """
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    ARCHIVED = "archived"


# ============================================================
# Dataset Metadata
# ============================================================
@dataclass
class DatasetMetadataV392:
    """
    数据集元数据。
    """
    dataset_name: str = ""
    start_date: str = ""
    end_date: str = ""
    universe_name: str = ""
    universe_size: Optional[int] = None
    frequency: str = "daily"
    data_source: str = ""
    data_version: str = ""
    adjusted_price: str = ""
    pit_enabled: bool = False
    available_date_column: str = ""
    survivorship_controlled: bool = False
    leakage_controlled: bool = False
    notes: str = ""


# ============================================================
# Alpha Metadata
# ============================================================
@dataclass
class AlphaMetadataV392:
    """
    Alpha 元数据。
    """
    alpha_id: str = ""
    formula: str = ""
    direction: str = "long"
    expression_hash: str = ""
    complexity: Optional[float] = None
    factor_names: list[str] = field(
        default_factory=list
    )
    operator_names: list[str] = field(
        default_factory=list
    )
    generation: Optional[int] = None
    parent_alpha_ids: list[str] = field(
        default_factory=list
    )
    notes: str = ""


# ============================================================
# Validation Metadata
# ============================================================
@dataclass
class ValidationMetadataV392:
    """
    Validation 状态。
    """
    schema_passed: Optional[bool] = None
    pit_passed: Optional[bool] = None
    leakage_passed: Optional[bool] = None
    survivorship_passed: Optional[bool] = None
    temporal_passed: Optional[bool] = None
    split_passed: Optional[bool] = None
    oos_passed: Optional[bool] = None
    walk_forward_passed: Optional[bool] = None
    final_passed: Optional[bool] = None
    audit_status: str = ""
    rejection_reason: str = ""


# ============================================================
# Backtest Metadata
# ============================================================
@dataclass
class BacktestMetadataV392:
    """
    回测指标。

    不负责计算，只负责存储。
    """
    ic_mean: Optional[float] = None
    ic_std: Optional[float] = None
    icir: Optional[float] = None
    positive_ic_ratio: Optional[float] = None
    q1_mean: Optional[float] = None
    q5_mean: Optional[float] = None
    q5_q1_mean: Optional[float] = None
    long_only_mean: Optional[float] = None
    average_turnover: Optional[float] = None
    total_transaction_cost: Optional[float] = None
    gross_return: Optional[float] = None
    net_return: Optional[float] = None
    cumulative_gross_return: Optional[float] = None
    cumulative_net_return: Optional[float] = None
    annualized_return: Optional[float] = None
    annualized_volatility: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    n_days: Optional[int] = None
    n_observations: Optional[int] = None


# ============================================================
# OOS Metadata
# ============================================================
@dataclass
class OOSMetadataV392:
    """
    Out-of-Sample 指标。
    """
    train_ic: Optional[float] = None
    validation_ic: Optional[float] = None
    test_ic: Optional[float] = None
    train_icir: Optional[float] = None
    validation_icir: Optional[float] = None
    test_icir: Optional[float] = None
    train_q5_q1: Optional[float] = None
    validation_q5_q1: Optional[float] = None
    test_q5_q1: Optional[float] = None
    train_days: Optional[int] = None
    validation_days: Optional[int] = None
    test_days: Optional[int] = None
    passed: Optional[bool] = None
    notes: str = ""


# ============================================================
# Walk Forward Metadata
# ============================================================
@dataclass
class WalkForwardMetadataV392:
    """
    Walk Forward 指标。
    """
    n_windows: Optional[int] = None
    passed_windows: Optional[int] = None
    window_pass_rate: Optional[float] = None
    mean_ic: Optional[float] = None
    mean_icir: Optional[float] = None
    mean_q5_q1: Optional[float] = None
    mean_turnover: Optional[float] = None
    direction_consistency: Optional[float] = None
    passed: Optional[bool] = None
    notes: str = ""


# ============================================================
# Experiment Record
# ============================================================
@dataclass
class ExperimentRecordV392:
    """
    一个完整实验记录。
    """
    experiment_id: str
    created_at: str
    updated_at: str
    status: str
    project_version: str
    git_commit: str
    python_version: str
    platform: str
    random_seed: Optional[int]
    dataset: DatasetMetadataV392
    alpha: AlphaMetadataV392
    validation: ValidationMetadataV392
    backtest: BacktestMetadataV392
    oos: OOSMetadataV392
    walk_forward: WalkForwardMetadataV392
    parameters: dict[str, Any]
    search_space: dict[str, Any]
    environment: dict[str, Any]
    config_hash: str
    result_hash: str = ""
    error: str = ""
    notes: str = ""
    tags: list[str] = field(
        default_factory=list
    )
    artifacts: dict[str, str] = field(
        default_factory=dict
    )

    # --------------------------------------------------------
    # Serialization
    # --------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "ExperimentRecordV392":
        dataset = DatasetMetadataV392(
            **data.get(
                "dataset",
                {},
            )
        )
        alpha = AlphaMetadataV392(
            **data.get(
                "alpha",
                {},
            )
        )
        validation = ValidationMetadataV392(
            **data.get(
                "validation",
                {},
            )
        )
        backtest = BacktestMetadataV392(
            **data.get(
                "backtest",
                {},
            )
        )
        oos = OOSMetadataV392(
            **data.get(
                "oos",
                {},
            )
        )
        walk_forward = (
            WalkForwardMetadataV392(
                **data.get(
                    "walk_forward",
                    {},
                )
            )
        )
        return cls(
            experiment_id=data["experiment_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            status=data["status"],
            project_version=data.get(
                "project_version",
                "",
            ),
            git_commit=data.get(
                "git_commit",
                "",
            ),
            python_version=data.get(
                "python_version",
                "",
            ),
            platform=data.get(
                "platform",
                "",
            ),
            random_seed=data.get(
                "random_seed"
            ),
            dataset=dataset,
            alpha=alpha,
            validation=validation,
            backtest=backtest,
            oos=oos,
            walk_forward=walk_forward,
            parameters=data.get(
                "parameters",
                {},
            ),
            search_space=data.get(
                "search_space",
                {},
            ),
            environment=data.get(
                "environment",
                {},
            ),
            config_hash=data.get(
                "config_hash",
                "",
            ),
            result_hash=data.get(
                "result_hash",
                "",
            ),
            error=data.get(
                "error",
                "",
            ),
            notes=data.get(
                "notes",
                "",
            ),
            tags=data.get(
                "tags",
                [],
            ),
            artifacts=data.get(
                "artifacts",
                {},
            ),
        )


# ============================================================
# Registry
# ============================================================
class ExperimentRegistryV392:
    """
    JSON 实验注册中心。

    默认：

        experiments/registry.json

    可以通过 path 修改。

    Example
    -------

        registry = ExperimentRegistryV392()

        record = registry.create(...)

        registry.save(record)

        result = registry.get(
            record.experiment_id
        )
    """

    def __init__(
        self,
        path: str | Path = (
            "experiments/registry.json"
        ),
    ):
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.records: dict[
            str,
            ExperimentRecordV392,
        ] = {}
        self.load()

    # ========================================================
    # Persistence
    # ========================================================
    def load(self) -> None:
        if not self.path.exists():
            self.records = {}
            return
        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as f:
                payload = json.load(f)
        except (
            json.JSONDecodeError,
            OSError,
        ):
            # Registry 损坏不能静默覆盖。
            raise RuntimeError(
                f"Unable to load registry: "
                f"{self.path}"
            )
        if isinstance(payload, dict):
            raw_records = payload.get(
                "records",
                [],
            )
        elif isinstance(payload, list):
            raw_records = payload
        else:
            raise ValueError(
                "Invalid registry format."
            )
        self.records = {}
        for raw in raw_records:
            record = (
                ExperimentRecordV392.from_dict(raw)
            )
            self.records[
                record.experiment_id
            ] = record

    def save_registry(self) -> None:
        payload = {
            "schema_version": "3.9.2",
            "updated_at": utc_now_iso_v392(),
            "records": [
                record.to_dict()
                for record in self.records.values()
            ],
        }
        temporary_path = (
            self.path.with_suffix(".tmp")
        )
        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        os.replace(
            temporary_path,
            self.path,
        )

    # ========================================================
    # Create
    # ========================================================
    def create(
        self,
        *,
        project_version: str = "V3.9.2",
        git_commit: str = "",
        random_seed: Optional[int] = None,
        dataset: Optional[DatasetMetadataV392] = None,
        alpha: Optional[AlphaMetadataV392] = None,
        validation: Optional[ValidationMetadataV392] = None,
        backtest: Optional[BacktestMetadataV392] = None,
        oos: Optional[OOSMetadataV392] = None,
        walk_forward: Optional[WalkForwardMetadataV392] = None,
        parameters: Optional[
            dict[str, Any]
        ] = None,
        search_space: Optional[
            dict[str, Any]
        ] = None,
        environment: Optional[
            dict[str, Any]
        ] = None,
        notes: str = "",
        tags: Optional[
            list[str]
        ] = None,
    ) -> ExperimentRecordV392:
        experiment_id = (
            make_experiment_id_v392()
        )
        created_at = utc_now_iso_v392()
        parameters = (
            parameters or {}
        )
        search_space = (
            search_space or {}
        )
        environment = (
            environment or {}
        )
        config_payload = {
            "project_version": (
                project_version
            ),
            "random_seed": (
                random_seed
            ),
            "dataset": asdict(
                dataset or DatasetMetadataV392()
            ),
            "alpha": asdict(
                alpha or AlphaMetadataV392()
            ),
            "parameters": parameters,
            "search_space": search_space,
        }
        config_hash = stable_hash_v392(
            config_payload
        )
        record = ExperimentRecordV392(
            experiment_id=experiment_id,
            created_at=created_at,
            updated_at=created_at,
            status=(
                ExperimentStatusV392.CREATED
            ),
            project_version=(
                project_version
            ),
            git_commit=git_commit,
            python_version=(
                sys.version
            ),
            platform=(
                platform.platform()
            ),
            random_seed=random_seed,
            dataset=(
                dataset or DatasetMetadataV392()
            ),
            alpha=(
                alpha or AlphaMetadataV392()
            ),
            validation=(
                validation or ValidationMetadataV392()
            ),
            backtest=(
                backtest or BacktestMetadataV392()
            ),
            oos=(
                oos or OOSMetadataV392()
            ),
            walk_forward=(
                walk_forward or WalkForwardMetadataV392()
            ),
            parameters=parameters,
            search_space=search_space,
            environment=environment,
            config_hash=config_hash,
            tags=tags or [],
            notes=notes,
        )
        self.records[experiment_id] = record
        return record

    # ========================================================
    # Get
    # ========================================================
    def get(
        self,
        experiment_id: str,
    ) -> ExperimentRecordV392:
        if (
            experiment_id
            not in self.records
        ):
            raise KeyError(
                f"Experiment not found: "
                f"{experiment_id}"
            )
        return self.records[experiment_id]

    # ========================================================
    # Exists
    # ========================================================
    def exists(
        self,
        experiment_id: str,
    ) -> bool:
        return (
            experiment_id in self.records
        )

    # ========================================================
    # Update
    # ========================================================
    def update(
        self,
        experiment_id: str,
        **updates: Any,
    ) -> ExperimentRecordV392:
        record = self.get(experiment_id)
        allowed = {
            "status",
            "git_commit",
            "dataset",
            "alpha",
            "validation",
            "backtest",
            "oos",
            "walk_forward",
            "parameters",
            "search_space",
            "environment",
            "error",
            "notes",
            "tags",
            "artifacts",
        }
        invalid = (
            set(updates) - allowed
        )
        if invalid:
            raise ValueError(
                "Unsupported experiment fields: "
                f"{sorted(invalid)}"
            )
        for key, value in (
            updates.items()
        ):
            if key in {
                "dataset",
                "alpha",
                "validation",
                "backtest",
                "oos",
                "walk_forward",
            }:
                expected_types = {
                    "dataset": DatasetMetadataV392,
                    "alpha": AlphaMetadataV392,
                    "validation": ValidationMetadataV392,
                    "backtest": BacktestMetadataV392,
                    "oos": OOSMetadataV392,
                    "walk_forward": WalkForwardMetadataV392,
                }
                expected = (
                    expected_types[key]
                )
                if isinstance(value, dict):
                    value = expected(
                        **value
                    )
                if not isinstance(
                    value,
                    expected,
                ):
                    raise TypeError(
                        f"{key} must be "
                        f"{expected.__name__}"
                    )
            setattr(
                record,
                key,
                value,
            )
        record.updated_at = (
            utc_now_iso_v392()
        )
        # 更新 result hash
        record.result_hash = (
            stable_hash_v392(
                {
                    "backtest": asdict(
                        record.backtest
                    ),
                    "oos": asdict(
                        record.oos
                    ),
                    "walk_forward": asdict(
                        record.walk_forward
                    ),
                    "validation": asdict(
                        record.validation
                    ),
                }
            )
        )
        return record

    # ========================================================
    # Save One
    # ========================================================
    def save(
        self,
        record: ExperimentRecordV392,
    ) -> None:
        if not isinstance(
            record,
            ExperimentRecordV392,
        ):
            raise TypeError(
                "record must be "
                "ExperimentRecordV392"
            )
        existing = self.records.get(
            record.experiment_id
        )
        if (
            existing is not None
            and existing.created_at
            != record.created_at
        ):
            raise ValueError(
                "Experiment ID collision."
            )
        record.updated_at = (
            utc_now_iso_v392()
        )
        self.records[
            record.experiment_id
        ] = record
        self.save_registry()

    # ========================================================
    # Delete
    # ========================================================
    def delete(
        self,
        experiment_id: str,
    ) -> None:
        if (
            experiment_id
            not in self.records
        ):
            raise KeyError(
                f"Experiment not found: "
                f"{experiment_id}"
            )
        del self.records[experiment_id]
        self.save_registry()

    # ========================================================
    # List
    # ========================================================
    def list(
        self,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[ExperimentRecordV392]:
        records = list(
            self.records.values()
        )
        if status is not None:
            records = [
                r for r in records
                if r.status == status
            ]
        if tag is not None:
            records = [
                r for r in records
                if tag in r.tags
            ]
        records.sort(
            key=lambda x: x.created_at,
            reverse=True,
        )
        if limit is not None:
            if limit < 0:
                raise ValueError(
                    "limit must be >= 0"
                )
            records = records[:limit]
        return records

    # ========================================================
    # Search
    # ========================================================
    def search(
        self,
        *,
        alpha_id: Optional[str] = None,
        formula: Optional[str] = None,
        dataset_name: Optional[str] = None,
        universe_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[ExperimentRecordV392]:
        """
        根据实验属性查询。
        """
        records = list(
            self.records.values()
        )
        if alpha_id is not None:
            records = [
                r for r in records
                if r.alpha.alpha_id == alpha_id
            ]
        if formula is not None:
            records = [
                r for r in records
                if r.alpha.formula == formula
            ]
        if dataset_name is not None:
            records = [
                r for r in records
                if r.dataset.dataset_name
                == dataset_name
            ]
        if universe_name is not None:
            records = [
                r for r in records
                if r.dataset.universe_name
                == universe_name
            ]
        if status is not None:
            records = [
                r for r in records
                if r.status == status
            ]
        records.sort(
            key=lambda x: x.created_at,
            reverse=True,
        )
        return records

    # ========================================================
    # Complete
    # ========================================================
    def complete(
        self,
        experiment_id: str,
        backtest: Optional[BacktestMetadataV392] = None,
        validation: Optional[ValidationMetadataV392] = None,
        oos: Optional[OOSMetadataV392] = None,
        walk_forward: Optional[WalkForwardMetadataV392] = None,
        notes: Optional[str] = None,
    ) -> ExperimentRecordV392:
        record = self.get(experiment_id)
        if backtest is not None:
            record.backtest = backtest
        if validation is not None:
            record.validation = validation
        if oos is not None:
            record.oos = oos
        if walk_forward is not None:
            record.walk_forward = (
                walk_forward
            )
        if notes is not None:
            record.notes = notes
        record.status = (
            ExperimentStatusV392.COMPLETED
        )
        record.updated_at = (
            utc_now_iso_v392()
        )
        record.result_hash = (
            stable_hash_v392(
                {
                    "backtest": asdict(
                        record.backtest
                    ),
                    "validation": asdict(
                        record.validation
                    ),
                    "oos": asdict(
                        record.oos
                    ),
                    "walk_forward": asdict(
                        record.walk_forward
                    ),
                }
            )
        )
        self.save_registry()
        return record

    # ========================================================
    # Fail
    # ========================================================
    def fail(
        self,
        experiment_id: str,
        error: str,
    ) -> ExperimentRecordV392:
        record = self.get(experiment_id)
        record.status = (
            ExperimentStatusV392.FAILED
        )
        record.error = str(error)
        record.updated_at = (
            utc_now_iso_v392()
        )
        self.save_registry()
        return record

    # ========================================================
    # Reject
    # ========================================================
    def reject(
        self,
        experiment_id: str,
        reason: str,
    ) -> ExperimentRecordV392:
        record = self.get(experiment_id)
        record.status = (
            ExperimentStatusV392.REJECTED
        )
        record.validation.rejection_reason = (
            str(reason)
        )
        record.updated_at = (
            utc_now_iso_v392()
        )
        self.save_registry()
        return record

    # ========================================================
    # Archive
    # ========================================================
    def archive(
        self,
        experiment_id: str,
    ) -> ExperimentRecordV392:
        record = self.get(experiment_id)
        record.status = (
            ExperimentStatusV392.ARCHIVED
        )
        record.updated_at = (
            utc_now_iso_v392()
        )
        self.save_registry()
        return record

    # ========================================================
    # Statistics
    # ========================================================
    def statistics(self) -> dict[str, Any]:
        records = list(
            self.records.values()
        )
        status_counts: dict[str, int] = {}
        for record in records:
            status_counts[
                record.status
            ] = (
                status_counts.get(
                    record.status,
                    0,
                )
                + 1
            )
        completed = [
            r for r in records
            if r.status
            == ExperimentStatusV392.COMPLETED
        ]
        rejected = [
            r for r in records
            if r.status
            == ExperimentStatusV392.REJECTED
        ]
        failed = [
            r for r in records
            if r.status
            == ExperimentStatusV392.FAILED
        ]
        ic_values = [
            r.backtest.ic_mean
            for r in completed
            if r.backtest.ic_mean is not None
        ]
        sharpe_values = [
            r.backtest.sharpe
            for r in completed
            if r.backtest.sharpe is not None
        ]
        return {
            "total_experiments": len(records),
            "status_counts": (
                status_counts
            ),
            "completed": len(completed),
            "rejected": len(rejected),
            "failed": len(failed),
            "mean_ic": (
                sum(ic_values) / len(ic_values)
                if ic_values
                else None
            ),
            "mean_sharpe": (
                sum(sharpe_values) / len(sharpe_values)
                if sharpe_values
                else None
            ),
        }


# ============================================================
# Result Adapter
# ============================================================
def backtest_result_to_metadata_v392(
    result: Any,
) -> BacktestMetadataV392:
    """
    将 AlphaBacktestResult
    转换成 Registry Metadata。

    使用 getattr，
    避免 Registry 强依赖 backtest 实现。
    """
    fields = {
        "ic_mean",
        "ic_std",
        "icir",
        "positive_ic_ratio",
        "q1_mean",
        "q5_mean",
        "q5_q1_mean",
        "long_only_mean",
        "average_turnover",
        "total_transaction_cost",
        "gross_return",
        "net_return",
        "cumulative_gross_return",
        "cumulative_net_return",
        "annualized_return",
        "annualized_volatility",
        "sharpe",
        "max_drawdown",
        "n_days",
        "n_observations",
    }
    values: dict[str, Any] = {}
    for field_name in fields:
        value = getattr(
            result,
            field_name,
            None,
        )
        if field_name in {
            "n_days",
            "n_observations",
        }:
            if value is not None:
                try:
                    value = int(value)
                except (
                    TypeError,
                    ValueError,
                ):
                    value = None
        else:
            value = safe_float_v392(
                value
            )
        values[field_name] = value
    return BacktestMetadataV392(
        **values
    )


# ============================================================
# OOS Adapter
# ============================================================
def oos_result_to_metadata_v392(
    result: Any,
) -> OOSMetadataV392:
    """
    将 OOS Validator 结果转换成 Metadata。

    支持不同实现，只要属性名称一致即可。
    """
    return OOSMetadataV392(
        train_ic=safe_float_v392(
            getattr(
                result,
                "train_ic",
                None,
            )
        ),
        validation_ic=safe_float_v392(
            getattr(
                result,
                "validation_ic",
                None,
            )
        ),
        test_ic=safe_float_v392(
            getattr(
                result,
                "test_ic",
                None,
            )
        ),
        train_icir=safe_float_v392(
            getattr(
                result,
                "train_icir",
                None,
            )
        ),
        validation_icir=safe_float_v392(
            getattr(
                result,
                "validation_icir",
                None,
            )
        ),
        test_icir=safe_float_v392(
            getattr(
                result,
                "test_icir",
                None,
            )
        ),
        train_q5_q1=safe_float_v392(
            getattr(
                result,
                "train_q5_q1",
                None,
            )
        ),
        validation_q5_q1=safe_float_v392(
            getattr(
                result,
                "validation_q5_q1",
                None,
            )
        ),
        test_q5_q1=safe_float_v392(
            getattr(
                result,
                "test_q5_q1",
                None,
            )
        ),
        train_days=(
            getattr(
                result,
                "train_days",
                None,
            )
        ),
        validation_days=(
            getattr(
                result,
                "validation_days",
                None,
            )
        ),
        test_days=(
            getattr(
                result,
                "test_days",
                None,
            )
        ),
        passed=getattr(
            result,
            "passed",
            None,
        ),
        notes=str(
            getattr(
                result,
                "notes",
                "",
            )
        ),
    )


# ============================================================
# Registry Summary DataFrame
# ============================================================
def registry_to_dataframe_v392(
    registry: ExperimentRegistryV392,
):
    """
    将实验 Registry 转换为 DataFrame。

    便于：

    - 排序
    - 筛选
    - 导出 CSV
    - Dashboard
    """
    import pandas as pd
    rows = []
    for record in registry.list():
        rows.append(
            {
                "experiment_id": (
                    record.experiment_id
                ),
                "created_at": (
                    record.created_at
                ),
                "status": record.status,
                "alpha_id": (
                    record.alpha.alpha_id
                ),
                "formula": (
                    record.alpha.formula
                ),
                "complexity": (
                    record.alpha.complexity
                ),
                "dataset": (
                    record.dataset.dataset_name
                ),
                "universe": (
                    record.dataset.universe_name
                ),
                "pit_enabled": (
                    record.dataset.pit_enabled
                ),
                "ic_mean": (
                    record.backtest.ic_mean
                ),
                "icir": (
                    record.backtest.icir
                ),
                "q5_q1": (
                    record.backtest.q5_q1_mean
                ),
                "turnover": (
                    record.backtest.average_turnover
                ),
                "net_return": (
                    record.backtest.net_return
                ),
                "sharpe": (
                    record.backtest.sharpe
                ),
                "max_drawdown": (
                    record.backtest.max_drawdown
                ),
                "oos_passed": (
                    record.oos.passed
                ),
                "walk_forward_passed": (
                    record.walk_forward.passed
                ),
                "final_passed": (
                    record.validation.final_passed
                ),
            }
        )
    return pd.DataFrame(rows)


# ============================================================
# Export
# ============================================================
def export_registry_v392(
    registry: ExperimentRegistryV392,
    path: str | Path,
) -> Path:
    """
    导出完整 Registry JSON。
    """
    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    payload = {
        "schema_version": "3.9.2",
        "exported_at": utc_now_iso_v392(),
        "records": [
            record.to_dict()
            for record in registry.list()
        ],
    }
    with path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    return path


# ============================================================
# Demo
# ============================================================
def _demo_v392() -> None:
    registry = ExperimentRegistryV392(
        "experiments/demo_registry.json"
    )
    dataset = DatasetMetadataV392(
        dataset_name="AshareDailyDemo",
        start_date="2020-01-01",
        end_date="2025-12-31",
        universe_name="CSI300",
        universe_size=300,
        frequency="daily",
        data_source="AkShare",
        data_version="demo",
        pit_enabled=True,
        available_date_column=(
            "available_date"
        ),
        survivorship_controlled=True,
        leakage_controlled=True,
    )
    alpha = AlphaMetadataV392(
        alpha_id="alpha_demo_001",
        formula="rank(roe) + rank(momentum_20)",
        direction="long",
        expression_hash=stable_hash_v392(
            "rank(roe)+rank(momentum_20)"
        ),
        complexity=4,
        factor_names=[
            "roe",
            "momentum_20",
        ],
        operator_names=[
            "rank",
            "add",
        ],
    )
    record = registry.create(
        dataset=dataset,
        alpha=alpha,
        random_seed=42,
        parameters={
            "horizon": 1,
            "quantiles": 5,
        },
        search_space={
            "max_depth": 4,
            "max_nodes": 12,
        },
        tags=[
            "demo",
            "v3.9.2",
        ],
        notes=(
            "Demo Alpha experiment"
        ),
    )
    print(
        "Created:",
        record.experiment_id,
    )
    registry.update(
        record.experiment_id,
        status=(
            ExperimentStatusV392.RUNNING
        ),
    )
    backtest = BacktestMetadataV392(
        ic_mean=0.035,
        ic_std=0.08,
        icir=0.4375,
        positive_ic_ratio=0.58,
        q1_mean=-0.001,
        q5_mean=0.002,
        q5_q1_mean=0.003,
        long_only_mean=0.002,
        average_turnover=0.35,
        total_transaction_cost=0.0008,
        gross_return=0.002,
        net_return=0.0012,
        cumulative_gross_return=0.25,
        cumulative_net_return=0.15,
        annualized_return=0.12,
        annualized_volatility=0.18,
        sharpe=0.67,
        max_drawdown=-0.15,
        n_days=1200,
        n_observations=300000,
    )
    validation = ValidationMetadataV392(
        schema_passed=True,
        pit_passed=True,
        leakage_passed=True,
        survivorship_passed=True,
        temporal_passed=True,
        split_passed=True,
        oos_passed=True,
        walk_forward_passed=True,
        final_passed=True,
        audit_status="PASS",
    )
    oos = OOSMetadataV392(
        train_ic=0.04,
        validation_ic=0.03,
        test_ic=0.025,
        train_icir=0.5,
        validation_icir=0.4,
        test_icir=0.32,
        train_q5_q1=0.004,
        validation_q5_q1=0.003,
        test_q5_q1=0.0025,
        train_days=700,
        validation_days=250,
        test_days=250,
        passed=True,
    )
    walk_forward = (
        WalkForwardMetadataV392(
            n_windows=10,
            passed_windows=7,
            window_pass_rate=0.7,
            mean_ic=0.028,
            mean_icir=0.35,
            mean_q5_q1=0.0027,
            mean_turnover=0.32,
            direction_consistency=0.8,
            passed=True,
        )
    )
    registry.complete(
        record.experiment_id,
        backtest=backtest,
        validation=validation,
        oos=oos,
        walk_forward=walk_forward,
    )
    registry.save_registry()
    print()
    print("Statistics:")
    print(
        json.dumps(
            registry.statistics(),
            ensure_ascii=False,
            indent=2,
        )
    )
    print()
    print("DataFrame:")
    print(
        registry_to_dataframe_v392(
            registry
        )
    )


# ============================================================
# Self Test
# ============================================================
def _self_test_v392() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = (
            Path(tmp) / "registry.json"
        )
        registry = (
            ExperimentRegistryV392(
                path
            )
        )
        dataset = DatasetMetadataV392(
            dataset_name="test",
            universe_name="TEST",
            pit_enabled=True,
        )
        alpha = AlphaMetadataV392(
            alpha_id="alpha_test",
            formula="rank(roe)",
            complexity=2,
        )
        record = registry.create(
            dataset=dataset,
            alpha=alpha,
            random_seed=42,
            parameters={
                "horizon": 1,
            },
            tags=[
                "test",
            ],
        )
        assert registry.exists(
            record.experiment_id
        )
        registry.update(
            record.experiment_id,
            status=(
                ExperimentStatusV392.RUNNING
            ),
        )
        backtest = BacktestMetadataV392(
            ic_mean=0.03,
            icir=0.4,
            q5_q1_mean=0.002,
            sharpe=1.0,
            max_drawdown=-0.1,
        )
        validation = ValidationMetadataV392(
            pit_passed=True,
            leakage_passed=True,
            final_passed=True,
        )
        registry.complete(
            record.experiment_id,
            backtest=backtest,
            validation=validation,
        )
        loaded = (
            ExperimentRegistryV392(
                path
            )
        )
        restored = loaded.get(
            record.experiment_id
        )
        assert (
            restored.alpha.alpha_id
            == "alpha_test"
        )
        assert (
            restored.backtest.ic_mean
            == 0.03
        )
        assert (
            restored.status
            == ExperimentStatusV392.COMPLETED
        )
        search_result = loaded.search(
            alpha_id="alpha_test"
        )
        assert len(search_result) == 1
        stats = (
            loaded.statistics()
        )
        assert (
            stats["total_experiments"] == 1
        )
        frame = (
            registry_to_dataframe_v392(
                loaded
            )
        )
        assert len(frame) == 1
        print(
            "experiments/registry.py "
            "V392 self-test passed."
        )


if __name__ == "__main__":
    _self_test_v392()
