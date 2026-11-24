from __future__ import annotations

from datetime import date

from data.universe import (
    HistoricalUniverse,
)


class SurvivorshipDetector:
    def __init__(
        self,
        universe: HistoricalUniverse,
    ):
        self.universe = universe

    def validate(
        self,
        codes: list[str],
        as_of_date: date,
    ):
        missing = []
        for code in codes:
            if not self.universe.is_active(
                code,
                as_of_date,
            ):
                missing.append(code)
        return {
            "valid": len(missing) == 0,
            "invalid_codes": missing,
        }



# ============================================================================
# V3.9.1 unified research engine - survivorship / universe validation
# ============================================================================


def validate_universe(panel: pd.DataFrame) -> list[str]:
    """幸存者偏差检查：检查 panel 中 code 是否在 date 之前上市/之后退市。
    需要 lifecycle 信息时调用 HistoricalUniverse.filter；此处仅做基本检查。"""
    errors: list[str] = []
    if panel is None or panel.empty:
        return errors
    if "code" not in panel.columns:
        errors.append("panel 缺少 code 列")
    return errors


# ============================================================================
# V3.9.2 survivorship bias audit - point-in-time universe / lifecycle
# ============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


class SurvivorshipErrorV392(Exception):
    """Base exception for survivorship-bias validation."""


class SurvivorshipViolationErrorV392(SurvivorshipErrorV392):
    """Raised when survivorship bias is detected under strict mode."""


class SurvivorshipStatusV392(str, Enum):
    OK = "ok"
    WARNING = "warning"
    VIOLATION = "violation"
    UNKNOWN = "unknown"


class UniverseModeV392(str, Enum):
    HISTORICAL = "historical"
    CURRENT = "current"
    STATIC = "static"


@dataclass
class SurvivorshipConfigV392:
    """
    Configuration for historical-universe / survivorship-bias audit.

    Required historical lifecycle columns:
        code
        date
        ipo_date
        delist_date

    Optional:
        list_date
        status
        is_active
        universe_date

    Important:
        current-only universe is prohibited in strict research mode.
    """

    code_column: str = "code"
    date_column: str = "date"
    ipo_date_column: str = "ipo_date"
    list_date_column: str = "list_date"
    delist_date_column: str = "delist_date"
    status_column: str = "status"
    active_column: str = "is_active"
    universe_date_column: str = "universe_date"

    strict: bool = True
    allow_current_universe: bool = False
    allow_static_universe: bool = False
    unknown_lifecycle_as_violation: bool = True
    require_ipo_date: bool = False
    require_delist_date: bool = False

    # If True, a stock whose IPO date is after the observation
    # date is excluded from the historical universe.
    enforce_ipo_boundary: bool = True
    # If True, a stock whose delist date is before the observation
    # date is excluded from the historical universe.
    enforce_delist_boundary: bool = True

    # Whether delist_date itself is considered tradable.
    # Normally the stock should not be treated as active after delist.
    delist_date_inclusive: bool = True
    # Whether IPO date itself is considered eligible.
    ipo_date_inclusive: bool = True

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SurvivorshipViolationV392:
    code: str
    date: Optional[str]
    violation_type: str
    message: str
    severity: str = "error"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "date": self.date,
            "violation_type": self.violation_type,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


@dataclass
class SurvivorshipAuditResultV392:
    status: SurvivorshipStatusV392
    rows_checked: int = 0
    unique_codes: int = 0
    violations: List[SurvivorshipViolationV392] = field(default_factory=list)
    warnings: List[SurvivorshipViolationV392] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def passed(self) -> bool:
        return self.status in {
            SurvivorshipStatusV392.OK,
            SurvivorshipStatusV392.WARNING,
        }

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def summary(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "rows_checked": self.rows_checked,
            "unique_codes": self.unique_codes,
            "violation_count": self.violation_count,
            "warning_count": self.warning_count,
            "diagnostics": self.diagnostics,
        }

    def raise_if_failed(self) -> None:
        if self.status == SurvivorshipStatusV392.VIOLATION:
            messages = [v.message for v in self.violations[:10]]
            raise SurvivorshipViolationErrorV392(
                "Survivorship audit failed:\n" + "\n".join(messages)
            )


def _normalize_code_v392(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.isdigit():
        return text.zfill(6)
    return text


def _normalize_date_series_v392(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def _date_to_string_v392(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def _safe_bool_v392(value: Any) -> Optional[bool]:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "active", "listed", "正常", "正常交易"}:
        return True
    if text in {"0", "false", "no", "n", "inactive", "delisted", "退市"}:
        return False
    return None


@dataclass
class SecurityLifecycleV392:
    code: str
    ipo_date: Optional[pd.Timestamp] = None
    list_date: Optional[pd.Timestamp] = None
    delist_date: Optional[pd.Timestamp] = None
    status: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_known(self) -> bool:
        return (
            self.ipo_date is not None
            or self.list_date is not None
            or self.delist_date is not None
        )

    def eligible(
        self,
        observation_date: pd.Timestamp,
        *,
        ipo_inclusive: bool = True,
        delist_inclusive: bool = True,
    ) -> bool:
        date = pd.Timestamp(observation_date).normalize()
        listing_date = self.ipo_date or self.list_date

        if listing_date is not None:
            listing_date = pd.Timestamp(listing_date).normalize()
            if ipo_inclusive:
                if date < listing_date:
                    return False
            else:
                if date <= listing_date:
                    return False

        if self.delist_date is not None:
            delist_date = pd.Timestamp(self.delist_date).normalize()
            if delist_inclusive:
                if date > delist_date:
                    return False
            else:
                if date >= delist_date:
                    return False

        return True


class HistoricalUniverseBuilderV392:
    """
    Construct point-in-time eligible securities.

    This class is intentionally independent of the data vendor.

    It can consume lifecycle data from:
        - AkShare
        - database
        - CSV
        - Parquet
        - internal security master
    """

    def __init__(self, config: Optional[SurvivorshipConfigV392] = None) -> None:
        self.config = config or SurvivorshipConfigV392()

    def prepare(self, lifecycle: pd.DataFrame) -> pd.DataFrame:
        if lifecycle is None:
            raise ValueError("lifecycle cannot be None")
        df = lifecycle.copy()
        code_col = self.config.code_column
        if code_col not in df.columns:
            raise ValueError(f"Missing lifecycle column: {code_col}")
        df[code_col] = df[code_col].map(_normalize_code_v392)
        for column in [
            self.config.ipo_date_column,
            self.config.list_date_column,
            self.config.delist_date_column,
        ]:
            if column in df.columns:
                df[column] = _normalize_date_series_v392(df[column])
        return df

    def build_lifecycles(
        self, lifecycle: pd.DataFrame
    ) -> Dict[str, SecurityLifecycleV392]:
        df = self.prepare(lifecycle)
        result: Dict[str, SecurityLifecycleV392] = {}
        for _, row in df.iterrows():
            code = _normalize_code_v392(row[self.config.code_column])
            if not code:
                continue

            ipo_date = None
            if self.config.ipo_date_column in row.index:
                value = row[self.config.ipo_date_column]
                if not pd.isna(value):
                    ipo_date = pd.Timestamp(value)

            list_date = None
            if self.config.list_date_column in row.index:
                value = row[self.config.list_date_column]
                if not pd.isna(value):
                    list_date = pd.Timestamp(value)

            delist_date = None
            if self.config.delist_date_column in row.index:
                value = row[self.config.delist_date_column]
                if not pd.isna(value):
                    delist_date = pd.Timestamp(value)

            status = ""
            if self.config.status_column in row.index:
                status = str(row[self.config.status_column])

            result[code] = SecurityLifecycleV392(
                code=code,
                ipo_date=ipo_date,
                list_date=list_date,
                delist_date=delist_date,
                status=status,
            )
        return result

    def universe_as_of(
        self, lifecycle: pd.DataFrame, as_of_date: Any
    ) -> List[str]:
        date = pd.Timestamp(as_of_date).normalize()
        lifecycles = self.build_lifecycles(lifecycle)
        result = []
        for code, security in lifecycles.items():
            if security.eligible(
                date,
                ipo_inclusive=self.config.ipo_date_inclusive,
                delist_inclusive=self.config.delist_date_inclusive,
            ):
                result.append(code)
        return sorted(result)

    def build_panel_universe(
        self, lifecycle: pd.DataFrame, dates: Iterable[Any]
    ) -> pd.DataFrame:
        lifecycles = self.build_lifecycles(lifecycle)
        rows = []
        for raw_date in dates:
            date = pd.Timestamp(raw_date).normalize()
            for code, security in lifecycles.items():
                eligible = security.eligible(
                    date,
                    ipo_inclusive=self.config.ipo_date_inclusive,
                    delist_inclusive=self.config.delist_date_inclusive,
                )
                if eligible:
                    rows.append(
                        {
                            "date": date,
                            "code": code,
                            "is_in_historical_universe": True,
                            "ipo_date": security.ipo_date,
                            "delist_date": security.delist_date,
                        }
                    )
        return pd.DataFrame(rows)


class SurvivorshipAuditorV392:
    """
    Audit whether a research dataset suffers from survivorship bias.

    Main checks:
        1. current universe used for historical backtest
        2. static universe used without historical membership
        3. securities appearing before IPO
        4. securities remaining after delisting
        5. missing lifecycle information
        6. mismatch between historical universe and observations
        7. current-status fields being used as historical status
    """

    def __init__(self, config: Optional[SurvivorshipConfigV392] = None) -> None:
        self.config = config or SurvivorshipConfigV392()

    def prepare_panel(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel is None:
            raise ValueError("panel cannot be None")
        df = panel.copy()
        required = [self.config.code_column, self.config.date_column]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                "Missing required panel columns: " + ", ".join(missing)
            )
        df[self.config.code_column] = df[self.config.code_column].map(
            _normalize_code_v392
        )
        df[self.config.date_column] = _normalize_date_series_v392(
            df[self.config.date_column]
        )
        return df

    def audit_universe_mode(
        self, universe_mode: Any
    ) -> List[SurvivorshipViolationV392]:
        if isinstance(universe_mode, UniverseModeV392):
            mode = universe_mode.value
        else:
            mode = str(universe_mode).lower()

        violations = []
        if (
            mode == UniverseModeV392.CURRENT.value
            and not self.config.allow_current_universe
        ):
            violations.append(
                SurvivorshipViolationV392(
                    code="",
                    date=None,
                    violation_type="current_universe",
                    message="Current stock universe was used for historical research.",
                    severity="error",
                )
            )
        if (
            mode == UniverseModeV392.STATIC.value
            and not self.config.allow_static_universe
        ):
            violations.append(
                SurvivorshipViolationV392(
                    code="",
                    date=None,
                    violation_type="static_universe",
                    message="Static stock universe was used without historical membership.",
                    severity="error",
                )
            )
        return violations

    def audit_lifecycle(
        self, panel: pd.DataFrame, lifecycle: pd.DataFrame
    ) -> SurvivorshipAuditResultV392:
        df = self.prepare_panel(panel)
        lifecycle_df = HistoricalUniverseBuilderV392(self.config).prepare(lifecycle)
        lifecycles = HistoricalUniverseBuilderV392(self.config).build_lifecycles(
            lifecycle_df
        )

        violations: List[SurvivorshipViolationV392] = []
        warnings: List[SurvivorshipViolationV392] = []
        rows_checked = 0
        unknown_codes = set()
        pre_ipo_count = 0
        post_delist_count = 0

        code_col = self.config.code_column
        date_col = self.config.date_column

        for _, row in df.iterrows():
            rows_checked += 1
            code = _normalize_code_v392(row[code_col])
            date = pd.Timestamp(row[date_col])

            if not code:
                warnings.append(
                    SurvivorshipViolationV392(
                        code="",
                        date=_date_to_string_v392(date),
                        violation_type="missing_code",
                        message="Observation has empty security code.",
                        severity="warning",
                    )
                )
                continue

            security = lifecycles.get(code)
            if security is None:
                unknown_codes.add(code)
                severity = (
                    "error"
                    if self.config.strict
                    and self.config.unknown_lifecycle_as_violation
                    else "warning"
                )
                item = SurvivorshipViolationV392(
                    code=code,
                    date=_date_to_string_v392(date),
                    violation_type="unknown_lifecycle",
                    message=f"No lifecycle information found for {code}.",
                    severity=severity,
                )
                if severity == "error":
                    violations.append(item)
                else:
                    warnings.append(item)
                continue

            # Before IPO
            listing_date = security.ipo_date or security.list_date
            if (
                self.config.enforce_ipo_boundary
                and listing_date is not None
            ):
                listing_date = pd.Timestamp(listing_date).normalize()
                invalid_before_ipo = (
                    date < listing_date
                    if self.config.ipo_date_inclusive
                    else date <= listing_date
                )
                if invalid_before_ipo:
                    pre_ipo_count += 1
                    violations.append(
                        SurvivorshipViolationV392(
                            code=code,
                            date=_date_to_string_v392(date),
                            violation_type="pre_ipo_observation",
                            message=(
                                f"{code} appears on {_date_to_string_v392(date)} "
                                f"before listing date {_date_to_string_v392(listing_date)}."
                            ),
                            severity="error",
                            details={"ipo_date": _date_to_string_v392(listing_date)},
                        )
                    )

            # After Delisting
            if (
                self.config.enforce_delist_boundary
                and security.delist_date is not None
            ):
                delist_date = pd.Timestamp(security.delist_date).normalize()
                invalid_after_delist = (
                    date > delist_date
                    if self.config.delist_date_inclusive
                    else date >= delist_date
                )
                if invalid_after_delist:
                    post_delist_count += 1
                    violations.append(
                        SurvivorshipViolationV392(
                            code=code,
                            date=_date_to_string_v392(date),
                            violation_type="post_delist_observation",
                            message=(
                                f"{code} appears on {_date_to_string_v392(date)} "
                                f"after delisting date {_date_to_string_v392(delist_date)}."
                            ),
                            severity="error",
                            details={"delist_date": _date_to_string_v392(delist_date)},
                        )
                    )

        diagnostics = {
            "unknown_code_count": len(unknown_codes),
            "pre_ipo_rows": pre_ipo_count,
            "post_delist_rows": post_delist_count,
        }
        status = self._status(violations, warnings)
        return SurvivorshipAuditResultV392(
            status=status,
            rows_checked=rows_checked,
            unique_codes=df[code_col].nunique(),
            violations=violations,
            warnings=warnings,
            diagnostics=diagnostics,
        )

    def audit_current_status_field(
        self, panel: pd.DataFrame
    ) -> List[SurvivorshipViolationV392]:
        violations = []
        suspicious_columns = {
            "is_active",
            "active",
            "current_status",
            "latest_status",
            "is_current",
        }
        found = suspicious_columns.intersection(set(panel.columns))
        for column in sorted(found):
            violations.append(
                SurvivorshipViolationV392(
                    code="",
                    date=None,
                    violation_type="current_status_field",
                    message=(
                        f"Panel contains '{column}', which may represent current "
                        f"security status rather than point-in-time status."
                    ),
                    severity="warning",
                    details={"column": column},
                )
            )
        return violations

    def audit_membership(
        self, panel: pd.DataFrame, historical_universe: pd.DataFrame
    ) -> SurvivorshipAuditResultV392:
        df = self.prepare_panel(panel)
        universe = historical_universe.copy()
        required = [self.config.code_column, self.config.date_column]
        missing = [col for col in required if col not in universe.columns]
        if missing:
            raise ValueError(
                "Historical universe missing columns: " + ", ".join(missing)
            )
        universe[self.config.code_column] = universe[
            self.config.code_column
        ].map(_normalize_code_v392)
        universe[self.config.date_column] = _normalize_date_series_v392(
            universe[self.config.date_column]
        )
        membership = set(
            zip(
                universe[self.config.date_column],
                universe[self.config.code_column],
            )
        )
        violations = []
        for _, row in df.iterrows():
            date = pd.Timestamp(row[self.config.date_column])
            code = _normalize_code_v392(row[self.config.code_column])
            if (date, code) not in membership:
                violations.append(
                    SurvivorshipViolationV392(
                        code=code,
                        date=_date_to_string_v392(date),
                        violation_type="universe_membership_mismatch",
                        message=(
                            f"{code} on {_date_to_string_v392(date)} "
                            f"is not present in the historical universe."
                        ),
                        severity="error",
                    )
                )
        status = self._status(violations, [])
        return SurvivorshipAuditResultV392(
            status=status,
            rows_checked=len(df),
            unique_codes=df[self.config.code_column].nunique(),
            violations=violations,
            diagnostics={
                "historical_membership_rows": len(universe),
            },
        )

    def audit(
        self,
        panel: pd.DataFrame,
        *,
        lifecycle: Optional[pd.DataFrame] = None,
        historical_universe: Optional[pd.DataFrame] = None,
        universe_mode: Any = UniverseModeV392.HISTORICAL,
    ) -> SurvivorshipAuditResultV392:
        df = self.prepare_panel(panel)
        violations: List[SurvivorshipViolationV392] = []
        warnings: List[SurvivorshipViolationV392] = []

        # Universe mode
        mode_issues = self.audit_universe_mode(universe_mode)
        violations.extend(
            [x for x in mode_issues if x.severity == "error"]
        )
        warnings.extend(
            [x for x in mode_issues if x.severity != "error"]
        )

        # Current status field
        status_issues = self.audit_current_status_field(df)
        warnings.extend(status_issues)

        # Lifecycle
        lifecycle_result = None
        if lifecycle is not None:
            lifecycle_result = self.audit_lifecycle(df, lifecycle)
            violations.extend(lifecycle_result.violations)
            warnings.extend(lifecycle_result.warnings)
        else:
            issue = SurvivorshipViolationV392(
                code="",
                date=None,
                violation_type="missing_lifecycle",
                message="No historical security lifecycle data was provided.",
                severity="error" if self.config.strict else "warning",
            )
            if issue.severity == "error":
                violations.append(issue)
            else:
                warnings.append(issue)

        # Historical membership
        membership_result = None
        if historical_universe is not None:
            membership_result = self.audit_membership(df, historical_universe)
            violations.extend(membership_result.violations)
            warnings.extend(membership_result.warnings)

        diagnostics = {
            "universe_mode": (
                universe_mode.value
                if isinstance(universe_mode, UniverseModeV392)
                else str(universe_mode)
            ),
            "lifecycle_provided": lifecycle is not None,
            "historical_universe_provided": historical_universe is not None,
            "current_status_warning_count": len(status_issues),
        }
        if lifecycle_result is not None:
            diagnostics["lifecycle_audit"] = lifecycle_result.summary()
        if membership_result is not None:
            diagnostics["membership_audit"] = membership_result.summary()

        status = self._status(violations, warnings)
        return SurvivorshipAuditResultV392(
            status=status,
            rows_checked=len(df),
            unique_codes=df[self.config.code_column].nunique(),
            violations=violations,
            warnings=warnings,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _status(
        violations: List[SurvivorshipViolationV392],
        warnings: List[SurvivorshipViolationV392],
    ) -> SurvivorshipStatusV392:
        if violations:
            return SurvivorshipStatusV392.VIOLATION
        if warnings:
            return SurvivorshipStatusV392.WARNING
        return SurvivorshipStatusV392.OK


def filter_historical_universe_v392(
    panel: pd.DataFrame,
    lifecycle: pd.DataFrame,
    config: Optional[SurvivorshipConfigV392] = None,
) -> pd.DataFrame:
    """
    Filter a panel to securities that existed at each date.

    IMPORTANT:
        This function does not create missing historical data.
        It only removes observations that are outside the
        security lifecycle.
    """
    config = config or SurvivorshipConfigV392()
    builder = HistoricalUniverseBuilderV392(config)
    lifecycles = builder.build_lifecycles(lifecycle)

    df = panel.copy()
    df[config.code_column] = df[config.code_column].map(_normalize_code_v392)
    df[config.date_column] = _normalize_date_series_v392(df[config.date_column])

    mask = []
    for _, row in df.iterrows():
        code = row[config.code_column]
        date = row[config.date_column]
        security = lifecycles.get(code)
        if security is None:
            mask.append(False)
            continue
        mask.append(
            security.eligible(
                date,
                ipo_inclusive=config.ipo_date_inclusive,
                delist_inclusive=config.delist_date_inclusive,
            )
        )
    return df.loc[np.asarray(mask)].copy()


def compare_universes_v392(
    current_universe: Iterable[str],
    historical_universe: Iterable[str],
) -> Dict[str, Any]:
    current = {
        _normalize_code_v392(x)
        for x in current_universe
        if _normalize_code_v392(x)
    }
    historical = {
        _normalize_code_v392(x)
        for x in historical_universe
        if _normalize_code_v392(x)
    }
    return {
        "current_count": len(current),
        "historical_count": len(historical),
        "overlap_count": len(current & historical),
        "only_current": sorted(current - historical),
        "only_historical": sorted(historical - current),
        "jaccard": (
            len(current & historical) / len(current | historical)
            if current | historical
            else 1.0
        ),
    }


def audit_survivorship_v392(
    panel: pd.DataFrame,
    *,
    lifecycle: Optional[pd.DataFrame] = None,
    historical_universe: Optional[pd.DataFrame] = None,
    universe_mode: Any = UniverseModeV392.HISTORICAL,
    config: Optional[SurvivorshipConfigV392] = None,
) -> SurvivorshipAuditResultV392:
    auditor = SurvivorshipAuditorV392(config)
    return auditor.audit(
        panel,
        lifecycle=lifecycle,
        historical_universe=historical_universe,
        universe_mode=universe_mode,
    )


def assert_no_survivorship_bias_v392(
    panel: pd.DataFrame,
    *,
    lifecycle: Optional[pd.DataFrame] = None,
    historical_universe: Optional[pd.DataFrame] = None,
    universe_mode: Any = UniverseModeV392.HISTORICAL,
    config: Optional[SurvivorshipConfigV392] = None,
) -> SurvivorshipAuditResultV392:
    result = audit_survivorship_v392(
        panel,
        lifecycle=lifecycle,
        historical_universe=historical_universe,
        universe_mode=universe_mode,
        config=config,
    )
    result.raise_if_failed()
    return result


def _self_test_v392() -> None:
    lifecycle = pd.DataFrame(
        {
            "code": ["000001", "000002", "000003"],
            "ipo_date": ["2010-01-01", "2015-01-01", "2010-01-01"],
            "delist_date": [None, None, "2020-01-01"],
        }
    )
    panel = pd.DataFrame(
        {
            "date": [
                "2018-01-01",
                "2018-01-01",
                "2018-01-01",
                "2019-01-01",
                "2021-01-01",
            ],
            "code": ["000001", "000002", "000003", "000002", "000003"],
            "close": [10, 20, 5, 21, 1],
        }
    )

    # Historical universe
    config = SurvivorshipConfigV392(strict=True)
    builder = HistoricalUniverseBuilderV392(config)
    universe_2012 = builder.universe_as_of(lifecycle, "2012-01-01")
    assert "000001" in universe_2012
    assert "000003" in universe_2012
    assert "000002" not in universe_2012

    universe_2021 = builder.universe_as_of(lifecycle, "2021-01-01")
    assert "000001" in universe_2021
    assert "000002" in universe_2021
    assert "000003" not in universe_2021

    # Audit should detect post-delist observation
    auditor = SurvivorshipAuditorV392(config)
    result = auditor.audit(
        panel,
        lifecycle=lifecycle,
        universe_mode=UniverseModeV392.HISTORICAL,
    )
    assert result.status == SurvivorshipStatusV392.VIOLATION
    assert any(
        x.violation_type == "post_delist_observation"
        for x in result.violations
    )

    # Filter
    filtered = filter_historical_universe_v392(panel, lifecycle, config)
    assert not (
        (filtered["code"] == "000003")
        & (pd.to_datetime(filtered["date"]) > pd.Timestamp("2020-01-01"))
    ).any()

    # Current universe should fail
    current_result = auditor.audit(
        panel.iloc[:1],
        lifecycle=lifecycle,
        universe_mode=UniverseModeV392.CURRENT,
    )
    assert current_result.status == SurvivorshipStatusV392.VIOLATION

    # Universe comparison
    comparison = compare_universes_v392(
        ["000001", "000002"],
        ["000001", "000003"],
    )
    assert comparison["overlap_count"] == 1
    assert comparison["current_count"] == 2
    assert comparison["historical_count"] == 2

    print("validation/survivorship.py V392 self-test passed.")


if __name__ == "__main__":
    _self_test_v392()
