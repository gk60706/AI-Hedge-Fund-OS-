from __future__ import annotations

import hashlib


class AlphaDeduplicator:
    def signature(self, expression):
        text = expression.to_string()
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    def deduplicate(self, expressions):
        seen = set()
        result = []
        for expression in expressions:
            signature = self.signature(expression)
            if signature in seen:
                continue
            seen.add(signature)
            result.append(expression)
        return result
# ============================================================================
# V3.9.1 unified research engine - canonical deduplicator (signal-aware)
# ============================================================================


class AlphaDeduplicatorV391:
    def __init__(self, correlation_threshold: float = 0.90):
        self.correlation_threshold = correlation_threshold
        self.signatures = set()
        self.signals = []

    def accept(self, expression, signal) -> bool:
        sig = signature(expression)
        if sig in self.signatures:
            return False
        for old_signal in self.signals:
            correlation = signal_correlation(signal, old_signal)
            if correlation == correlation and abs(correlation) >= self.correlation_threshold:
                return False
        self.signatures.add(sig)
        self.signals.append(signal)
        return True


from alpha.canonical import signature  # noqa: E402
from alpha.correlation import signal_correlation  # noqa: E402


# ============================================================
# V3.9.2 Alpha Deduplicator (appended, V392 suffix)
# ============================================================

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import hashlib
import math
import numpy as np
import pandas as pd

from alpha.expression import AlphaExpression  # noqa: E402


class AlphaDeduplicationErrorV392(Exception):
    """Alpha 去重基础异常。"""


class AlphaDeduplicationInputErrorV392(AlphaDeduplicationErrorV392):
    """Alpha 去重输入错误。"""


@dataclass
class DeduplicationConfigV392:
    """
    Alpha 去重配置。
    """
    correlation_threshold: float = 0.90
    use_absolute_correlation: bool = True
    min_obs: int = 30
    constant_precision: int = 8
    structural_dedup: bool = True
    signal_dedup: bool = True
    id_field: str = "alpha_id"
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not (0.0 <= self.correlation_threshold <= 1.0):
            raise ValueError("correlation_threshold 必须位于 0~1")
        if self.min_obs < 2:
            raise ValueError("min_obs 必须 >= 2")
        if self.constant_precision < 0:
            raise ValueError("constant_precision 不能小于 0")


@dataclass
class DeduplicationResultV392:
    """
    Alpha 去重结果。
    """
    accepted: List[AlphaExpression]
    rejected: List[AlphaExpression]
    rejection_reasons: Dict[str, str]
    structural_duplicates: Dict[str, str]
    correlation_duplicates: Dict[str, str]
    correlations: Dict[Tuple[str, str], float]
    diagnostics: Dict = field(default_factory=dict)

    def summary(self) -> Dict:
        return {
            "input_count": len(self.accepted) + len(self.rejected),
            "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected),
            "structural_duplicate_count": len(self.structural_duplicates),
            "correlation_duplicate_count": len(self.correlation_duplicates),
        }


def _safe_float_v392(value, precision: int = 8):
    """
    将常数标准化。
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    if not np.isfinite(value):
        return str(value)
    value = round(value, precision)
    if value == 0:
        value = 0.0
    return value


def _safe_corr_v392(
    x: pd.Series,
    y: pd.Series,
    min_obs: int = 30,
    absolute: bool = True,
) -> float:
    df = pd.concat([x, y], axis=1).replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if len(df) < min_obs:
        return np.nan
    x_values = df.iloc[:, 0]
    y_values = df.iloc[:, 1]
    if x_values.nunique() <= 1:
        return np.nan
    if y_values.nunique() <= 1:
        return np.nan
    corr = float(x_values.corr(y_values))
    if not np.isfinite(corr):
        return np.nan
    if absolute:
        return abs(corr)
    return corr


def _expression_operator_v392(expression: AlphaExpression) -> str:
    return str(getattr(expression, "operator", ""))


def _expression_children_v392(expression: AlphaExpression) -> Sequence:
    children = getattr(expression, "children", None)
    if children is None:
        return []
    return children


def _expression_value_v392(expression: AlphaExpression):
    return getattr(expression, "value", None)


def _expression_feature_v392(expression: AlphaExpression):
    return getattr(expression, "feature", None)


class ExpressionCanonicalizerV392:
    """
    将 AlphaExpression 转换成规范化结构。
    """
    COMMUTATIVE_OPERATORS = {"add", "mul", "+", "*"}
    OPERATOR_ALIASES = {
        "+": "add", "add": "add",
        "-": "sub", "sub": "sub",
        "*": "mul", "mul": "mul",
        "/": "div", "div": "div",
        "neg": "neg", "negative": "neg",
        "abs": "abs", "log": "log",
        "rank": "rank", "zscore": "zscore",
    }

    def __init__(self, constant_precision: int = 8):
        self.constant_precision = constant_precision

    def normalize_operator(self, operator) -> str:
        operator = str(operator).lower()
        return self.OPERATOR_ALIASES.get(operator, operator)

    def canonical(self, expression: AlphaExpression) -> Tuple:
        operator = self.normalize_operator(_expression_operator_v392(expression))
        feature = _expression_feature_v392(expression)
        value = _expression_value_v392(expression)
        children = list(_expression_children_v392(expression))

        if not children:
            if feature is not None:
                return ("feature", str(feature))
            if value is not None:
                return ("value", _safe_float_v392(value, self.constant_precision))
            return ("node", operator)

        normalized_children = [self.canonical(child) for child in children]

        if operator in self.COMMUTATIVE_OPERATORS:
            normalized_children = sorted(normalized_children, key=lambda x: repr(x))

        return ("op", operator, tuple(normalized_children))

    def canonical_string(self, expression: AlphaExpression) -> str:
        return repr(self.canonical(expression))

    def fingerprint(self, expression: AlphaExpression) -> str:
        canonical = self.canonical_string(expression)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AlphaSignalStoreV392:
    """
    保存 Alpha signal。
    """

    def __init__(
        self,
        date_column: str = "date",
        code_column: str = "code",
        alpha_id_column: str = "alpha_id",
        signal_column: str = "signal",
    ):
        self.date_column = date_column
        self.code_column = code_column
        self.alpha_id_column = alpha_id_column
        self.signal_column = signal_column
        self._signals: Dict[str, pd.Series] = {}

    def add(self, alpha_id: str, data: pd.DataFrame):
        required = [self.date_column, self.code_column, self.signal_column]
        missing = [c for c in required if c not in data.columns]
        if missing:
            raise AlphaDeduplicationInputErrorV392(f"signal 数据缺少字段: {missing}")
        df = data[required].copy()
        df[self.date_column] = pd.to_datetime(
            df[self.date_column], errors="coerce"
        )
        df[self.code_column] = df[self.code_column].astype(str)
        df[self.signal_column] = pd.to_numeric(
            df[self.signal_column], errors="coerce"
        )
        index = pd.MultiIndex.from_frame(
            df[[self.date_column, self.code_column]]
        )
        signal = pd.Series(
            df[self.signal_column].to_numpy(),
            index=index,
            name=alpha_id,
        )
        self._signals[str(alpha_id)] = signal

    def get(self, alpha_id: str) -> Optional[pd.Series]:
        return self._signals.get(str(alpha_id))

    def contains(self, alpha_id: str) -> bool:
        return str(alpha_id) in self._signals

    def ids(self) -> List[str]:
        return list(self._signals.keys())


def pairwise_signal_correlation_v392(
    signals: Dict[str, pd.Series],
    min_obs: int = 30,
    absolute: bool = True,
) -> pd.DataFrame:
    ids = list(signals.keys())
    matrix = pd.DataFrame(
        np.nan, index=ids, columns=ids, dtype=float
    )
    for alpha_id in ids:
        matrix.loc[alpha_id, alpha_id] = 1.0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            left = ids[i]
            right = ids[j]
            corr = _safe_corr_v392(
                signals[left], signals[right],
                min_obs=min_obs, absolute=absolute,
            )
            matrix.loc[left, right] = corr
            matrix.loc[right, left] = corr
    return matrix


class AlphaDeduplicatorV392:
    """
    Alpha 去重主引擎。
    """

    def __init__(
        self,
        config: Optional[DeduplicationConfigV392] = None,
    ):
        self.config = config or DeduplicationConfigV392()
        self.canonicalizer = ExpressionCanonicalizerV392(
            constant_precision=self.config.constant_precision
        )

    def fingerprint(self, alpha: AlphaExpression) -> str:
        return self.canonicalizer.fingerprint(alpha)

    def structural_dedup(
        self,
        alphas: Sequence[AlphaExpression],
    ) -> Tuple[List[AlphaExpression], Dict[str, str]]:
        accepted = []
        fingerprints: Dict[str, str] = {}
        duplicates: Dict[str, str] = {}
        for alpha in alphas:
            alpha_id = self.alpha_id(alpha)
            fingerprint = self.fingerprint(alpha)
            if fingerprint in fingerprints:
                duplicates[alpha_id] = fingerprints[fingerprint]
                continue
            fingerprints[fingerprint] = alpha_id
            accepted.append(alpha)
        return accepted, duplicates

    def alpha_id(self, alpha: AlphaExpression) -> str:
        existing = getattr(alpha, "alpha_id", None)
        if existing:
            return str(existing)
        return "alpha_" + self.fingerprint(alpha)[:16]

    def signal_dedup(
        self,
        alphas: Sequence[AlphaExpression],
        signals: Dict[str, pd.Series],
    ) -> Tuple[
        List[AlphaExpression],
        Dict[str, str],
        Dict[Tuple[str, str], float],
    ]:
        accepted = []
        rejected: Dict[str, str] = {}
        correlations: Dict[Tuple[str, str], float] = {}
        accepted_ids: List[str] = []

        for alpha in alphas:
            alpha_id = self.alpha_id(alpha)
            signal = signals.get(alpha_id)
            if signal is None:
                accepted.append(alpha)
                accepted_ids.append(alpha_id)
                continue

            duplicate_of = None
            for accepted_alpha in accepted:
                accepted_id = self.alpha_id(accepted_alpha)
                accepted_signal = signals.get(accepted_id)
                if accepted_signal is None:
                    continue
                corr = _safe_corr_v392(
                    signal, accepted_signal,
                    min_obs=self.config.min_obs,
                    absolute=self.config.use_absolute_correlation,
                )
                correlations[(alpha_id, accepted_id)] = corr
                if (
                    np.isfinite(corr)
                    and corr >= self.config.correlation_threshold
                ):
                    duplicate_of = accepted_id
                    break

            if duplicate_of:
                rejected[alpha_id] = duplicate_of
            else:
                accepted.append(alpha)
                accepted_ids.append(alpha_id)

        return accepted, rejected, correlations

    def deduplicate(
        self,
        alphas: Sequence[AlphaExpression],
        signals: Optional[Dict[str, pd.Series]] = None,
    ) -> DeduplicationResultV392:
        input_alphas = list(alphas)
        if not input_alphas:
            return DeduplicationResultV392(
                accepted=[],
                rejected=[],
                rejection_reasons={},
                structural_duplicates={},
                correlation_duplicates={},
                correlations={},
                diagnostics={"input_count": 0},
            )

        structural_duplicates = {}

        if self.config.structural_dedup:
            structurally_unique, structural_duplicates = self.structural_dedup(
                input_alphas
            )
        else:
            structurally_unique = input_alphas

        rejected = []
        rejection_reasons = {}
        for alpha_id, duplicate_of in structural_duplicates.items():
            for alpha in input_alphas:
                if self.alpha_id(alpha) == alpha_id:
                    rejected.append(alpha)
                    rejection_reasons[alpha_id] = (
                        "structural_duplicate:" + duplicate_of
                    )
                    break

        correlation_duplicates = {}
        correlations = {}
        if self.config.signal_dedup and signals:
            signal_unique, correlation_duplicates, correlations = self.signal_dedup(
                structurally_unique, signals,
            )
        else:
            signal_unique = structurally_unique

        for alpha_id, duplicate_of in correlation_duplicates.items():
            for alpha in structurally_unique:
                if self.alpha_id(alpha) == alpha_id:
                    rejected.append(alpha)
                    rejection_reasons[alpha_id] = (
                        "signal_correlation_duplicate:" + duplicate_of
                    )
                    break

        diagnostics = {
            "input_count": len(input_alphas),
            "structurally_unique_count": len(structurally_unique),
            "final_unique_count": len(signal_unique),
            "structural_duplicate_count": len(structural_duplicates),
            "correlation_duplicate_count": len(correlation_duplicates),
            "correlation_threshold": self.config.correlation_threshold,
        }

        return DeduplicationResultV392(
            accepted=signal_unique,
            rejected=rejected,
            rejection_reasons=rejection_reasons,
            structural_duplicates=structural_duplicates,
            correlation_duplicates=correlation_duplicates,
            correlations=correlations,
            diagnostics=diagnostics,
        )


def deduplicate_alphas_v392(
    alphas: Sequence[AlphaExpression],
    signals: Optional[Dict[str, pd.Series]] = None,
    config: Optional[DeduplicationConfigV392] = None,
) -> DeduplicationResultV392:
    engine = AlphaDeduplicatorV392(config=config)
    return engine.deduplicate(alphas, signals=signals)


def build_alpha_correlation_matrix_v392(
    signals: Dict[str, pd.Series],
    config: Optional[DeduplicationConfigV392] = None,
) -> pd.DataFrame:
    config = config or DeduplicationConfigV392()
    return pairwise_signal_correlation_v392(
        signals,
        min_obs=config.min_obs,
        absolute=config.use_absolute_correlation,
    )


def _make_feature_expression_v392(feature: str) -> AlphaExpression:
    return AlphaExpression(
        operator="feature",
        children=[],
        feature=feature,
    )


def _make_binary_v392(
    operator: str,
    left: AlphaExpression,
    right: AlphaExpression,
) -> AlphaExpression:
    return AlphaExpression(
        operator=operator,
        children=[left, right],
    )


def _self_test_v392():
    print("Running alpha.deduplicator self-test...")

    momentum = _make_feature_expression_v392("momentum_20")
    roe = _make_feature_expression_v392("roe")
    pb = _make_feature_expression_v392("pb_inverse")

    alpha_a = _make_binary_v392("add", momentum, roe)
    alpha_b = _make_binary_v392("add", roe, momentum)
    alpha_c = _make_binary_v392("sub", momentum, roe)
    alpha_d = _make_binary_v392("add", momentum, pb)

    engine = AlphaDeduplicatorV392(
        DeduplicationConfigV392(
            correlation_threshold=0.90,
            min_obs=20,
        )
    )

    unique, duplicates = engine.structural_dedup(
        [alpha_a, alpha_b, alpha_c, alpha_d]
    )
    assert len(unique) == 3
    assert len(duplicates) == 1
    print("Structural dedup PASSED.")

    rng = np.random.default_rng(123)
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    codes = [f"{i:06d}" for i in range(50)]
    index = pd.MultiIndex.from_product(
        [dates, codes], names=["date", "code"]
    )
    base = rng.normal(0, 1, len(index))
    signal_a = pd.Series(base, index=index, name="A")
    signal_b = pd.Series(
        base + rng.normal(0, 0.001, len(index)),
        index=index, name="B",
    )
    signal_c = pd.Series(
        rng.normal(0, 1, len(index)),
        index=index, name="C",
    )

    ids = {
        engine.alpha_id(alpha_a): alpha_a,
        engine.alpha_id(alpha_c): alpha_c,
        engine.alpha_id(alpha_d): alpha_d,
    }
    id_list = list(ids.keys())
    signals = {
        id_list[0]: signal_a,
        id_list[1]: signal_b,
        id_list[2]: signal_c,
    }

    result = engine.deduplicate(
        list(ids.values()),
        signals=signals,
    )

    print("\n=== Dedup Summary ===")
    print(result.summary())
    print("\n=== Diagnostics ===")
    print(result.diagnostics)
    assert result.diagnostics["correlation_duplicate_count"] >= 1

    matrix = build_alpha_correlation_matrix_v392(
        signals,
        DeduplicationConfigV392(min_obs=20),
    )
    print("\n=== Correlation Matrix ===")
    print(matrix)
    assert matrix.shape == (3, 3)
    assert np.isclose(matrix.iloc[0, 1], 1.0, atol=0.01)

    print("\nalpha.deduplicator self-test PASSED.")


if __name__ == "__main__":
    _self_test_v392()
