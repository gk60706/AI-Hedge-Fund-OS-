from __future__ import annotations

from datetime import date

from data.universe import (
    HistoricalUniverse,
)
from validation.survivorship import (
    SurvivorshipDetector,
)


class BacktestAudit:
    def __init__(
        self,
        universe: HistoricalUniverse,
    ):
        self.universe = universe

    def audit_universe(
        self,
        codes: list[str],
        as_of_date: date,
    ):
        detector = (
            SurvivorshipDetector(
                self.universe
            )
        )
        return detector.validate(
            codes,
            as_of_date,
        )

    def final_report(
        self,
        universe_result,
        lookahead_result=None,
        leakage_result=None,
    ):
        passed = (
            universe_result["valid"]
            and (
                lookahead_result is None
                or lookahead_result["valid"]
            )
            and (
                leakage_result is None
                or leakage_result["valid"]
            )
        )
        return {
            "passed": passed,
            "universe": universe_result,
            "lookahead": (lookahead_result),
            "leakage": (leakage_result),
        }
# ============================================================================
# V3.9.1 unified research engine - full audit (dump)
# ============================================================================


def full_audit(df, target_col=None):
    result = {
        "data_quality": audit_panel(df),
        "lookahead_rows": int(len(find_lookahead(df))),
    }
    if target_col:
        result["leakage"] = leakage_checks(df, target_col)
    else:
        result["leakage"] = []
    return result


from validation.data_quality import audit_panel  # noqa: E402
from validation.leakage import leakage_checks  # noqa: E402
from validation.lookahead import find_lookahead  # noqa: E402


# ============================================================================
# V3.9.2 Unified Research Audit Engine
# ============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from validation.leakage import (
    LeakageAuditResultV392,
    LeakageAuditorV392,
    LeakageConfigV392,
)
from validation.survivorship import (
    SurvivorshipAuditResultV392,
    SurvivorshipAuditorV392,
    SurvivorshipConfigV392,
)
from validation.temporal import (
    TemporalAuditResultV392,
    TemporalConfigV392,
    TemporalValidatorV392,
)
from validation.split import (
    DataSplitV392,
    SplitAuditResultV392,
    SplitConfigV392,
    TemporalDataSplitterV392,
)
from validation.walk_forward import (
    WalkForwardResultV392,
    WalkForwardValidatorV392,
    WalkForwardConfigV392,
)


class ResearchAuditErrorV392(Exception):
    """Research Audit 基础异常。"""


class ResearchAuditFailedV392(ResearchAuditErrorV392):
    """研究审计失败。"""


class ResearchAuditConfigErrorV392(ResearchAuditErrorV392):
    """Research Audit 配置错误。"""


class AuditStageV392(str, Enum):
    """
    审计阶段。
    """
    SCHEMA = "schema"
    POINT_IN_TIME = "point_in_time"
    LEAKAGE = "leakage"
    SURVIVORSHIP = "survivorship"
    TEMPORAL = "temporal"
    SPLIT = "split"
    WALK_FORWARD = "walk_forward"
    FINAL = "final"


@dataclass
class AuditStageResultV392:
    """
    单个审计阶段结果。
    """
    stage: AuditStageV392
    passed: bool = True
    errors: List[str] = field(
        default_factory=list
    )
    warnings: List[str] = field(
        default_factory=list
    )
    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )

    def add_error(
        self,
        message: str,
    ) -> None:
        self.errors.append(message)
        self.passed = False

    def add_warning(
        self,
        message: str,
    ) -> None:
        self.warnings.append(message)

    def summary(self) -> str:
        status = (
            "PASSED" if self.passed else "FAILED"
        )
        return (
            f"{self.stage.value}: "
            f"{status}; "
            f"errors={len(self.errors)}, "
            f"warnings={len(self.warnings)}"
        )


@dataclass
class ResearchAuditReportV392:
    """
    整个研究审计报告。
    """
    passed: bool = True
    stages: Dict[str, AuditStageResultV392] = field(
        default_factory=dict
    )
    errors: List[str] = field(
        default_factory=list
    )
    warnings: List[str] = field(
        default_factory=list
    )
    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def add_stage(
        self,
        result: AuditStageResultV392,
    ) -> None:
        self.stages[result.stage.value] = result
        if not result.passed:
            self.passed = False
            self.errors.extend(
                [
                    f"[{result.stage.value}]{error}"
                    for error in result.errors
                ]
            )
        self.warnings.extend(
            [
                f"[{result.stage.value}]{warning}"
                for warning in result.warnings
            ]
        )

    def finalize(self) -> None:
        self.passed = (len(self.errors) == 0)
        self.diagnostics.update(
            {
                "stage_count": len(self.stages),
                "failed_stage_count": sum(
                    1
                    for stage in self.stages.values()
                    if not stage.passed
                ),
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
            }
        )

    def raise_if_failed(self) -> None:
        if not self.passed:
            message = (
                "Research Audit FAILED\n"
                + "\n".join(self.errors)
            )
            raise ResearchAuditFailedV392(message)

    def summary(self) -> str:
        status = (
            "PASSED" if self.passed else "FAILED"
        )
        return (
            f"ResearchAudit[{status}] "
            f"stages={len(self.stages)}, "
            f"errors={len(self.errors)}, "
            f"warnings={len(self.warnings)}"
        )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "stages": {
                name: {
                    "stage": stage.stage.value,
                    "passed": stage.passed,
                    "errors": stage.errors,
                    "warnings": stage.warnings,
                    "diagnostics": stage.diagnostics,
                }
                for name, stage in self.stages.items()
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "diagnostics": self.diagnostics,
            "metadata": self.metadata,
        }

    def stage_passed(
        self,
        stage: AuditStageV392,
    ) -> bool:
        result = self.stages.get(stage.value)
        if result is None:
            return False
        return result.passed


@dataclass
class ResearchAuditConfigV392:
    """
    统一 Research Audit 配置。
    """
    date_column: str = "date"
    code_column: str = "code"
    available_date_column: str = (
        "available_date"
    )
    strict: bool = True
    run_schema: bool = True
    run_point_in_time: bool = True
    run_leakage: bool = True
    run_survivorship: bool = True
    run_temporal: bool = True
    run_split: bool = True
    run_walk_forward: bool = False
    leakage_config: LeakageConfigV392 = (
        field(default_factory=LeakageConfigV392)
    )
    survivorship_config: SurvivorshipConfigV392 = (
        field(default_factory=SurvivorshipConfigV392)
    )
    temporal_config: TemporalConfigV392 = (
        field(default_factory=TemporalConfigV392)
    )
    split_config: SplitConfigV392 = (
        field(default_factory=SplitConfigV392)
    )
    walk_forward_config: WalkForwardConfigV392 = (
        field(default_factory=WalkForwardConfigV392)
    )
    required_columns: Sequence[str] = field(
        default_factory=lambda: (
            "date",
            "code",
        )
    )

    def __post_init__(self) -> None:
        if not self.date_column:
            raise ResearchAuditConfigErrorV392(
                "date_column 不能为空"
            )
        if not self.code_column:
            raise ResearchAuditConfigErrorV392(
                "code_column 不能为空"
            )


class SchemaAuditorV392:
    """
    基础 DataFrame Schema 审计。
    """

    def __init__(
        self,
        config: ResearchAuditConfigV392,
    ) -> None:
        self.config = config

    def audit(
        self,
        df: pd.DataFrame,
    ) -> AuditStageResultV392:
        result = AuditStageResultV392(
            stage=AuditStageV392.SCHEMA
        )
        if not isinstance(df, pd.DataFrame):
            result.add_error(
                "输入数据不是 pandas.DataFrame。"
            )
            return result
        if df.empty:
            result.add_error(
                "输入 DataFrame 为空。"
            )
            return result
        required = set(self.config.required_columns)
        missing = [
            column
            for column in required
            if column not in df.columns
        ]
        if missing:
            result.add_error(
                "缺少必要字段: "
                + ", ".join(missing)
            )
        date_col = (self.config.date_column)
        if date_col in df.columns:
            parsed = pd.to_datetime(
                df[date_col],
                errors="coerce",
            )
            invalid_count = int(
                parsed.isna().sum()
            )
            if invalid_count > 0:
                result.add_error(
                    f"{date_col} 存在 "
                    f"{invalid_count} 个非法日期。"
                )
        code_col = (self.config.code_column)
        if code_col in df.columns:
            null_count = int(
                df[code_col].isna().sum()
            )
            if null_count > 0:
                result.add_error(
                    f"{code_col} 存在 "
                    f"{null_count} 个空值。"
                )
        if (
            date_col in df.columns
            and code_col in df.columns
        ):
            duplicate_count = int(
                df.duplicated(
                    subset=[
                        date_col,
                        code_col,
                    ],
                    keep=False,
                ).sum()
            )
            if duplicate_count > 0:
                result.add_error(
                    "发现重复 date + code "
                    f"记录: {duplicate_count} 行"
                )
        result.diagnostics.update(
            {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
            }
        )
        return result


class PointInTimeAuditorV392:
    """
    独立 PIT 审计。
    """

    def __init__(
        self,
        date_column: str,
        available_date_column: str,
        strict: bool = True,
    ) -> None:
        self.date_column = date_column
        self.available_date_column = (
            available_date_column
        )
        self.strict = strict

    def audit(
        self,
        df: pd.DataFrame,
    ) -> AuditStageResultV392:
        result = AuditStageResultV392(
            stage=AuditStageV392.POINT_IN_TIME
        )
        date_col = (self.date_column)
        available_col = (
            self.available_date_column
        )
        if date_col not in df.columns:
            result.add_error(
                f"缺少 signal date: {date_col}"
            )
            return result
        if available_col not in df.columns:
            message = (
                f"缺少 PIT 字段: {available_col}"
            )
            if self.strict:
                result.add_error(message)
            else:
                result.add_warning(message)
            return result
        signal_dates = pd.to_datetime(
            df[date_col],
            errors="coerce",
        )
        available_dates = pd.to_datetime(
            df[available_col],
            errors="coerce",
        )
        invalid_available = (
            available_dates.isna()
        )
        invalid_count = int(
            invalid_available.sum()
        )
        if invalid_count > 0:
            message = (
                f"{available_col} 存在 "
                f"{invalid_count} 个无法解析日期。"
            )
            if self.strict:
                result.add_error(message)
            else:
                result.add_warning(message)
        future_mask = (
            available_dates > signal_dates
        )
        future_count = int(
            future_mask.fillna(False).sum()
        )
        if future_count > 0:
            result.add_error(
                "发现 PIT Look-ahead："
                f"{future_count} 行 "
                "available_date > signal_date"
            )
        result.diagnostics.update(
            {
                "rows": len(df),
                "invalid_available_dates": (
                    invalid_count
                ),
                "future_available_dates": (
                    future_count
                ),
            }
        )
        return result


def _convert_generic_result_v392(
    stage: AuditStageV392,
    source_result: Any,
) -> AuditStageResultV392:
    result = AuditStageResultV392(stage=stage)
    if hasattr(source_result, "passed"):
        result.passed = bool(source_result.passed)
    if hasattr(source_result, "errors"):
        result.errors.extend(
            list(source_result.errors)
        )
    if hasattr(source_result, "warnings"):
        result.warnings.extend(
            list(source_result.warnings)
        )
    if hasattr(source_result, "diagnostics"):
        diagnostics = (source_result.diagnostics)
        if isinstance(diagnostics, dict):
            result.diagnostics.update(diagnostics)
    return result


class ResearchAuditorV392:
    """
    V3.9.2 统一研究审计器。
    """

    def __init__(
        self,
        config: Optional[
            ResearchAuditConfigV392
        ] = None,
    ) -> None:
        self.config = (
            config or ResearchAuditConfigV392()
        )
        self.schema_auditor = (
            SchemaAuditorV392(self.config)
        )
        self.pit_auditor = (
            PointInTimeAuditorV392(
                date_column=(
                    self.config.date_column
                ),
                available_date_column=(
                    self.config.available_date_column
                ),
                strict=self.config.strict,
            )
        )
        self.leakage_auditor = (
            LeakageAuditorV392(
                self.config.leakage_config
            )
        )
        self.survivorship_auditor = (
            SurvivorshipAuditorV392(
                self.config.survivorship_config
            )
        )
        self.temporal_validator = (
            TemporalValidatorV392(
                self.config.temporal_config
            )
        )
        self.splitter = (
            TemporalDataSplitterV392(
                self.config.split_config
            )
        )

    def audit_schema(
        self,
        df: pd.DataFrame,
    ) -> AuditStageResultV392:
        return self.schema_auditor.audit(df)

    def audit_point_in_time(
        self,
        df: pd.DataFrame,
    ) -> AuditStageResultV392:
        return self.pit_auditor.audit(df)

    def audit_leakage(
        self,
        df: pd.DataFrame,
    ) -> AuditStageResultV392:
        source_result = (
            self.leakage_auditor.audit(df)
        )
        return _convert_generic_result_v392(
            AuditStageV392.LEAKAGE,
            source_result,
        )

    def audit_survivorship(
        self,
        df: pd.DataFrame,
    ) -> AuditStageResultV392:
        source_result = (
            self.survivorship_auditor.audit(df)
        )
        return _convert_generic_result_v392(
            AuditStageV392.SURVIVORSHIP,
            source_result,
        )

    def audit_temporal(
        self,
        df: pd.DataFrame,
    ) -> AuditStageResultV392:
        try:
            source_result = (
                self.temporal_validator.validate_dataset(
                    df
                )
            )
            return _convert_generic_result_v392(
                AuditStageV392.TEMPORAL,
                source_result,
            )
        except Exception as exc:
            result = AuditStageResultV392(
                stage=AuditStageV392.TEMPORAL
            )
            result.add_error(str(exc))
            return result

    def audit_split(
        self,
        df: pd.DataFrame,
    ) -> tuple[
        AuditStageResultV392,
        List[DataSplitV392],
    ]:
        result = AuditStageResultV392(
            stage=AuditStageV392.SPLIT
        )
        try:
            splits = (
                self.splitter.split_all(df)
            )
            source_result = (
                self.splitter.audit_all(splits)
            )
            result = _convert_generic_result_v392(
                AuditStageV392.SPLIT,
                source_result,
            )
            result.diagnostics["window_count"] = (
                len(splits)
            )
            return result, splits
        except Exception as exc:
            result.add_error(str(exc))
            return result, []

    def audit_walk_forward(
        self,
        df: pd.DataFrame,
        signal_column: str,
        return_column: str,
        alpha_id: Optional[str] = None,
    ) -> tuple[
        AuditStageResultV392,
        Optional[WalkForwardResultV392],
    ]:
        result = AuditStageResultV392(
            stage=AuditStageV392.WALK_FORWARD
        )
        try:
            validator = (
                WalkForwardValidatorV392(
                    self.config.walk_forward_config
                )
            )
            wf_result = (
                validator.run(
                    df=df,
                    signal_column=signal_column,
                    return_column=return_column,
                    alpha_id=alpha_id,
                )
            )
            result.passed = (wf_result.passed)
            result.errors.extend(wf_result.errors)
            result.warnings.extend(
                wf_result.warnings
            )
            result.diagnostics.update(
                {
                    "window_count": len(
                        wf_result.windows
                    ),
                    "aggregate_metrics": (
                        wf_result.aggregate_metrics
                    ),
                }
            )
            return result, wf_result
        except Exception as exc:
            result.add_error(str(exc))
            return result, None

    def audit(
        self,
        df: pd.DataFrame,
        signal_column: Optional[str] = None,
        return_column: Optional[str] = None,
        alpha_id: Optional[str] = None,
    ) -> ResearchAuditReportV392:
        report = ResearchAuditReportV392(
            metadata={
                "date_column": (
                    self.config.date_column
                ),
                "code_column": (
                    self.config.code_column
                ),
                "strict": (self.config.strict),
            }
        )
        # ====================================================
        # 1. Schema
        # ====================================================
        if self.config.run_schema:
            schema_result = (
                self.audit_schema(df)
            )
            report.add_stage(schema_result)
            if (
                self.config.strict
                and not schema_result.passed
            ):
                report.finalize()
                return report
        # ====================================================
        # 2. PIT
        # ====================================================
        if self.config.run_point_in_time:
            pit_result = (
                self.audit_point_in_time(df)
            )
            report.add_stage(pit_result)
        # ====================================================
        # 3. Leakage
        # ====================================================
        if self.config.run_leakage:
            leakage_result = (
                self.audit_leakage(df)
            )
            report.add_stage(leakage_result)
        # ====================================================
        # 4. Survivorship
        # ====================================================
        if self.config.run_survivorship:
            survivorship_result = (
                self.audit_survivorship(df)
            )
            report.add_stage(survivorship_result)
        # ====================================================
        # 5. Temporal
        # ====================================================
        if self.config.run_temporal:
            temporal_result = (
                self.audit_temporal(df)
            )
            report.add_stage(temporal_result)
        # ====================================================
        # 6. Split
        # ====================================================
        splits: List[DataSplitV392] = []
        if self.config.run_split:
            split_result, splits = (
                self.audit_split(df)
            )
            report.add_stage(split_result)
        # ====================================================
        # 7. Walk Forward
        # ====================================================
        if (
            self.config.run_walk_forward
            and signal_column
            and return_column
        ):
            wf_result, wf = (
                self.audit_walk_forward(
                    df=df,
                    signal_column=signal_column,
                    return_column=return_column,
                    alpha_id=alpha_id,
                )
            )
            report.add_stage(wf_result)
            if wf is not None:
                report.diagnostics["walk_forward"] = (
                    wf.summary()
                )
        elif self.config.run_walk_forward:
            stage = AuditStageResultV392(
                stage=AuditStageV392.WALK_FORWARD
            )
            stage.add_warning(
                "未提供 signal_column / "
                "return_column，"
                "跳过 Walk Forward 指标审计。"
            )
            report.add_stage(stage)
        # ====================================================
        # Final
        # ====================================================
        final_stage = AuditStageResultV392(
            stage=AuditStageV392.FINAL
        )
        if report.errors:
            final_stage.add_error(
                "Research Audit 存在失败阶段。"
            )
        else:
            final_stage.diagnostics["message"] = (
                "所有启用的 Research Audit "
                "阶段均通过。"
            )
        report.add_stage(final_stage)
        report.finalize()
        report.diagnostics["split_count"] = len(splits)
        return report


def research_audit_v392(
    df: pd.DataFrame,
    config: Optional[
        ResearchAuditConfigV392
    ] = None,
    signal_column: Optional[str] = None,
    return_column: Optional[str] = None,
    alpha_id: Optional[str] = None,
) -> ResearchAuditReportV392:
    auditor = ResearchAuditorV392(config)
    return auditor.audit(
        df=df,
        signal_column=signal_column,
        return_column=return_column,
        alpha_id=alpha_id,
    )


def assert_research_ready_v392(
    df: pd.DataFrame,
    config: Optional[
        ResearchAuditConfigV392
    ] = None,
) -> ResearchAuditReportV392:
    report = research_audit_v392(
        df,
        config=config,
    )
    report.raise_if_failed()
    return report


class ResearchGateV392:
    """
    Research Gate。
    """

    def check(
        self,
        report: ResearchAuditReportV392,
    ) -> bool:
        return report.passed

    def assert_ready(
        self,
        report: ResearchAuditReportV392,
    ) -> None:
        if not report.passed:
            raise ResearchAuditFailedV392(
                "数据未通过 Research Gate。\n"
                + "\n".join(report.errors)
            )


def audit_report_to_frame_v392(
    report: ResearchAuditReportV392,
) -> pd.DataFrame:
    rows = []
    for stage_name, stage in (
        report.stages.items()
    ):
        rows.append(
            {
                "stage": stage_name,
                "passed": stage.passed,
                "error_count": len(stage.errors),
                "warning_count": len(
                    stage.warnings
                ),
                "errors": " | ".join(stage.errors),
                "warnings": " | ".join(
                    stage.warnings
                ),
            }
        )
    return pd.DataFrame(rows)


def _build_demo_data_v392(
    periods: int = 160,
    stocks: int = 20,
) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(
        "2024-01-01",
        periods=periods,
    )
    rows = []
    for date in dates:
        for i in range(stocks):
            code = (
                f"{600000 + i:06d}"
            )
            alpha = rng.normal()
            forward_return = (
                alpha * 0.02
                + rng.normal(scale=0.10)
            )
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "available_date": date,
                    "alpha": alpha,
                    "forward_return": (
                        forward_return
                    ),
                }
            )
    return pd.DataFrame(rows)


def self_test_v392() -> None:
    """
    模块自检。
    """
    df = _build_demo_data_v392()
    config = ResearchAuditConfigV392(
        strict=False,
        run_schema=True,
        run_point_in_time=True,
        run_leakage=False,
        run_survivorship=False,
        run_temporal=False,
        run_split=True,
        run_walk_forward=True,
        split_config=SplitConfigV392(
            min_train_periods=60,
            validation_periods=20,
            test_periods=20,
            step_periods=20,
            purge_periods=2,
            embargo_periods=2,
        ),
        walk_forward_config=(
            WalkForwardConfigV392(
                min_valid_windows=2,
                min_ic=0.0,
                min_icir=0.0,
                min_direction_consistency=0.0,
                min_window_pass_rate=0.0,
                strict_audit=True,
                split_config=SplitConfigV392(
                    min_train_periods=60,
                    validation_periods=20,
                    test_periods=20,
                    step_periods=20,
                    purge_periods=2,
                    embargo_periods=2,
                ),
            )
        ),
    )
    report = research_audit_v392(
        df=df,
        config=config,
        signal_column="alpha",
        return_column="forward_return",
        alpha_id="DEMO_ALPHA",
    )
    assert report.passed
    assert (
        report.stage_passed(AuditStageV392.SCHEMA)
    )
    assert (
        report.stage_passed(
            AuditStageV392.POINT_IN_TIME
        )
    )
    assert (
        report.stage_passed(AuditStageV392.SPLIT)
    )
    assert (
        report.stage_passed(
            AuditStageV392.WALK_FORWARD
        )
    )
    frame = audit_report_to_frame_v392(report)
    assert not frame.empty
    # --------------------------------------------------------
    # 测试 PIT 泄漏
    # --------------------------------------------------------
    bad_df = df.copy()
    bad_df.loc[
        bad_df.index[0],
        "available_date",
    ] = (
        bad_df.loc[
            bad_df.index[0],
            "date",
        ]
        + pd.Timedelta(days=1)
    )
    pit_config = ResearchAuditConfigV392(
        strict=True,
        run_schema=True,
        run_point_in_time=True,
        run_leakage=False,
        run_survivorship=False,
        run_temporal=False,
        run_split=False,
        run_walk_forward=False,
    )
    bad_report = research_audit_v392(
        bad_df,
        config=pit_config,
    )
    assert not bad_report.passed
    assert any(
        "PIT" in error
        or "available_date" in error
        for error in bad_report.errors
    )
    print(
        "validation/audit.py V392 self_test PASSED"
    )
    print(report.summary())


if __name__ == "__main__":
    self_test_v392()
