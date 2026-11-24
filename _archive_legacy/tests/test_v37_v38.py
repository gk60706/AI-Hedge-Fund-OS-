# -*- coding: utf-8 -*-
"""Tests for V3.7 Point-in-Time & Bias Control and V3.8 AI Alpha Research Engine."""
import os
import json
import tempfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

# ---- V3.7: data layer ----
from data.point_in_time import PITRecord, PointInTimeStore
from data.universe import SecurityLifecycle, HistoricalUniverse
from data.corporate_actions import CorporateAction, CorporateActionStore
from data.availability import DataAvailability, AvailabilityChecker

# ---- V3.7: validation layer ----
from validation.lookahead import LookaheadDetector
from validation.leakage import LeakageDetector
from validation.temporal import TemporalValidator
from validation.survivorship import SurvivorshipDetector
from validation.audit import BacktestAudit

# ---- V3.7: backtest layer ----
from backtest.dataset import CleanBacktestDataset

# ---- V3.8: factors ----
from factors.base import Factor
from factors.value import PEFactor, PBFactor, PSFactor
from factors.momentum import MomentumFactor, Momentum60Factor, Momentum120Factor
from factors.quality import ROEFactor, ROICFactor, RevenueGrowthFactor, ProfitGrowthFactor
from factors.volatility import VolatilityFactor
from factors.liquidity import TurnoverFactor, Amount20Factor
from factors.factory import FactorFactory
from factors.registry import FactorRegistry

# ---- V3.8: alpha ----
from alpha.ic import InformationCoefficient
from alpha.icir import ICIRCalculator
from alpha.quantile import QuantileAnalyzer
from alpha.decay import FactorDecayAnalyzer
from alpha.correlation import FactorCorrelation
from alpha.orthogonal import Orthogonalizer
from alpha.scorer import AlphaScorer

# ---- V3.8: experiments ----
from experiments.factor_test import FactorExperiment
from experiments.experiment import ExperimentStore


# =====================================================================
# V3.7 - data/point_in_time.py
# =====================================================================
class TestPointInTime:
    def test_effective_date_falls_back_to_publish(self):
        rec = PITRecord(code="300394", period_end=date(2023, 12, 31),
                        value=100, publish_date=date(2024, 3, 28))
        assert rec.effective_date() == date(2024, 3, 28)

    def test_effective_date_prefers_available(self):
        rec = PITRecord(code="300394", period_end=date(2023, 12, 31),
                        value=100, publish_date=date(2024, 3, 28),
                        available_date=date(2024, 4, 1))
        assert rec.effective_date() == date(2024, 4, 1)

    def test_query_not_visible_before_publish(self):
        store = PointInTimeStore()
        store.add(PITRecord(code="300394", period_end=date(2023, 12, 31),
                            value=100, publish_date=date(2024, 3, 28)))
        assert store.query("300394", date(2024, 3, 1)) is None

    def test_query_visible_after_publish(self):
        store = PointInTimeStore()
        rec = PITRecord(code="300394", period_end=date(2023, 12, 31),
                        value=100, publish_date=date(2024, 3, 28))
        store.add(rec)
        assert store.query("300394", date(2024, 4, 1)) is rec

    def test_query_returns_latest_period(self):
        store = PointInTimeStore()
        old = PITRecord(code="300394", period_end=date(2022, 12, 31),
                        value=50, publish_date=date(2023, 3, 30))
        new = PITRecord(code="300394", period_end=date(2023, 12, 31),
                        value=100, publish_date=date(2024, 3, 28))
        store.add(old)
        store.add(new)
        assert store.query("300394", date(2024, 4, 1)) is new

    def test_query_does_not_mix_codes(self):
        store = PointInTimeStore()
        store.add(PITRecord(code="600000", period_end=date(2023, 12, 31),
                            value=1, publish_date=date(2024, 3, 28)))
        assert store.query("300394", date(2024, 4, 1)) is None

    def test_query_many_returns_all_available(self):
        store = PointInTimeStore()
        a = PITRecord(code="300394", period_end=date(2022, 12, 31),
                      value=50, publish_date=date(2023, 3, 30))
        b = PITRecord(code="300394", period_end=date(2023, 12, 31),
                      value=100, publish_date=date(2024, 3, 28))
        store.add(a)
        store.add(b)
        assert len(store.query_many("300394", date(2024, 4, 1))) == 2
        assert len(store.query_many("300394", date(2024, 3, 1))) == 1


# =====================================================================
# V3.7 - data/universe.py
# =====================================================================
class TestUniverse:
    def _universe(self):
        u = HistoricalUniverse()
        u.add(SecurityLifecycle(code="300394", ipo_date=date(2016, 1, 1),
                                name="天孚通信"))
        u.add(SecurityLifecycle(code="600000", ipo_date=date(1999, 11, 10),
                                delist_date=date(2020, 6, 30), name="已退市"))
        return u

    def test_is_active_normal(self):
        assert self._universe().is_active("300394", date(2024, 1, 10)) is True

    def test_is_active_before_ipo(self):
        assert self._universe().is_active("300394", date(2015, 12, 31)) is False

    def test_is_active_after_delist(self):
        assert self._universe().is_active("600000", date(2020, 6, 30)) is False
        assert self._universe().is_active("600000", date(2020, 6, 29)) is True

    def test_is_active_unknown_code(self):
        assert self._universe().is_active("999999", date(2024, 1, 10)) is False

    def test_active_codes(self):
        u = self._universe()
        codes = u.active_codes(date(2020, 1, 1))
        assert "300394" in codes
        assert "600000" in codes
        codes = u.active_codes(date(2020, 7, 1))
        assert "600000" not in codes


# =====================================================================
# V3.7 - data/corporate_actions.py
# =====================================================================
class TestCorporateActions:
    def test_query_filters_by_ex_date(self):
        store = CorporateActionStore()
        a = CorporateAction(code="300394", ex_date=date(2024, 5, 20),
                            action_type="dividend", cash_dividend=0.5)
        b = CorporateAction(code="300394", ex_date=date(2024, 8, 10),
                            action_type="split", split_factor=2.0)
        store.add(a)
        store.add(b)
        assert store.query("300394", date(2024, 6, 1)) == [a]
        assert len(store.query("300394", date(2024, 9, 1))) == 2
        assert store.query("600000", date(2024, 9, 1)) == []


# =====================================================================
# V3.7 - data/availability.py
# =====================================================================
class TestAvailability:
    def test_is_available(self):
        checker = AvailabilityChecker()
        item = DataAvailability(field="roe", period_end=date(2023, 12, 31),
                                publish_date=date(2024, 3, 28),
                                available_date=date(2024, 4, 1))
        assert checker.is_available(item, date(2024, 4, 1)) is True
        assert checker.is_available(item, date(2024, 3, 31)) is False

    def test_assert_available_raises_on_leak(self):
        checker = AvailabilityChecker()
        item = DataAvailability(field="roe", period_end=date(2023, 12, 31),
                                publish_date=date(2024, 3, 28),
                                available_date=date(2024, 4, 1))
        with pytest.raises(ValueError):
            checker.assert_available(item, date(2024, 3, 31))


# =====================================================================
# V3.7 - validation/lookahead.py
# =====================================================================
class TestLookahead:
    def test_valid_no_violations(self):
        df = pd.DataFrame({
            "date": ["2024-03-01", "2024-04-01"],
            "available_date": ["2024-03-01", "2024-04-01"],
        })
        result = LookaheadDetector().detect(df)
        assert result["valid"] is True
        assert result["violations"] == 0

    def test_violation_when_available_after_date(self):
        df = pd.DataFrame({
            "date": ["2024-03-01"],
            "available_date": ["2024-04-01"],
        })
        result = LookaheadDetector().detect(df)
        assert result["valid"] is False
        assert result["violations"] == 1

    def test_missing_columns(self):
        df = pd.DataFrame({"date": ["2024-03-01"]})
        result = LookaheadDetector().detect(df)
        assert result["valid"] is False
        assert "error" in result


# =====================================================================
# V3.7 - validation/leakage.py
# =====================================================================
class TestLeakage:
    def test_valid_dataset(self):
        df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02"],
            "pe": [10.0, 11.0],
            "ret": [0.01, 0.02],
        })
        result = LeakageDetector().check_feature_target(df, ["pe"], "ret")
        assert result["valid"] is True
        assert result["issues"] == []

    def test_missing_date(self):
        df = pd.DataFrame({"pe": [1.0]})
        result = LeakageDetector().check_feature_target(df, ["pe"], "ret")
        assert result["valid"] is False
        assert "MISSING_DATE" in result["issues"]

    def test_date_not_sorted(self):
        df = pd.DataFrame({
            "date": ["2024-01-02", "2024-01-01"],
            "pe": [1.0, 2.0],
            "ret": [0.01, 0.02],
        })
        result = LeakageDetector().check_feature_target(df, ["pe"], "ret")
        assert "DATE_NOT_SORTED" in result["issues"]

    def test_missing_target_and_feature(self):
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "pe": [1.0],
        })
        result = LeakageDetector().check_feature_target(df, ["pe", "pb"], "ret")
        assert "MISSING_TARGET" in result["issues"]
        assert "MISSING_FEATURE:pb" in result["issues"]


# =====================================================================
# V3.7 - validation/temporal.py
# =====================================================================
class TestTemporal:
    def test_feature_before_label_valid(self):
        df = pd.DataFrame({
            "feature_date": ["2024-01-10"],
            "label_date": ["2024-01-11"],
        })
        result = TemporalValidator().validate(df, "feature_date", "label_date")
        assert result["valid"] is True

    def test_feature_after_label_is_leakage(self):
        df = pd.DataFrame({
            "feature_date": ["2024-01-11"],
            "label_date": ["2024-01-10"],
        })
        result = TemporalValidator().validate(df, "feature_date", "label_date")
        assert result["valid"] is False
        assert result["violations"] == 1


# =====================================================================
# V3.7 - validation/survivorship.py & audit.py
# =====================================================================
class TestSurvivorship:
    def _universe(self):
        u = HistoricalUniverse()
        u.add(SecurityLifecycle(code="300394", ipo_date=date(2016, 1, 1)))
        u.add(SecurityLifecycle(code="600000", ipo_date=date(1999, 11, 10),
                                delist_date=date(2020, 6, 30)))
        return u

    def test_all_active(self):
        result = SurvivorshipDetector(self._universe()).validate(
            ["300394"], date(2024, 1, 10))
        assert result["valid"] is True
        assert result["invalid_codes"] == []

    def test_delisted_detected(self):
        result = SurvivorshipDetector(self._universe()).validate(
            ["300394", "600000"], date(2024, 1, 10))
        assert result["valid"] is False
        assert result["invalid_codes"] == ["600000"]


class TestBacktestAudit:
    def _universe(self):
        u = HistoricalUniverse()
        u.add(SecurityLifecycle(code="300394", ipo_date=date(2016, 1, 1)))
        return u

    def test_audit_universe(self):
        result = BacktestAudit(self._universe()).audit_universe(
            ["300394"], date(2024, 1, 10))
        assert result["valid"] is True

    def test_final_report_passes(self):
        audit = BacktestAudit(self._universe())
        universe_result = {"valid": True}
        lookahead_result = {"valid": True}
        leakage_result = {"valid": True}
        report = audit.final_report(universe_result, lookahead_result, leakage_result)
        assert report["passed"] is True

    def test_final_report_fails_on_lookahead(self):
        audit = BacktestAudit(self._universe())
        report = audit.final_report({"valid": True}, {"valid": False}, {"valid": True})
        assert report["passed"] is False

    def test_final_report_none_tolerated(self):
        audit = BacktestAudit(self._universe())
        report = audit.final_report({"valid": True})
        assert report["passed"] is True
        assert report["lookahead"] is None
        assert report["leakage"] is None


# =====================================================================
# V3.7 - backtest/dataset.py
# =====================================================================
class TestCleanDataset:
    def test_filter_available(self):
        ds = CleanBacktestDataset("2024-03-01")
        df = pd.DataFrame({
            "available_date": ["2024-02-01", "2024-03-01", "2024-04-01"],
            "v": [1, 2, 3],
        })
        out = ds.filter_available(df)
        assert list(out["v"]) == [1, 2]

    def test_remove_duplicates(self):
        ds = CleanBacktestDataset("2024-03-01")
        df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
        out = ds.remove_duplicates(df)
        assert len(out) == 2

    def test_clean_resets_index(self):
        ds = CleanBacktestDataset("2024-03-01")
        df = pd.DataFrame({
            "available_date": ["2024-04-01", "2024-02-01", "2024-02-01"],
            "v": [1, 2, 3],
        })
        out = ds.clean(df)
        assert list(out.index) == [0, 1]
        assert list(out["v"]) == [2, 3]


# =====================================================================
# V3.8 - factors
# =====================================================================
def _factor_data(n=200):
    rng = np.random.default_rng(7)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0.001, 0.01, n)))
    return pd.DataFrame({
        "close": close,
        "pe": rng.uniform(5, 100, n),
        "pb": rng.uniform(0.5, 10, n),
        "ps": rng.uniform(0.5, 20, n),
        "roe": rng.normal(0.10, 0.05, n),
        "roic": rng.normal(0.08, 0.04, n),
        "revenue_growth": rng.normal(0.15, 0.20, n),
        "profit_growth": rng.normal(0.15, 0.30, n),
        "turnover": rng.uniform(0.5, 10, n),
        "amount": rng.uniform(1e7, 1e9, n),
    })


class TestValueFactors:
    def test_pe_inverse(self):
        data = _factor_data()
        factor = PEFactor()
        out = factor.calculate(data)
        assert factor.name == "pe_inverse"
        assert np.allclose(out.dropna(), 1.0 / data["pe"])

    def test_pe_nonpositive_becomes_nan(self):
        data = pd.DataFrame({"pe": [10.0, -5.0, 0.0, 20.0]})
        out = PEFactor().calculate(data)
        assert np.isnan(out.iloc[1])
        assert np.isnan(out.iloc[2])
        assert not np.isnan(out.iloc[0])

    def test_pb_ps_inverse(self):
        data = _factor_data()
        assert np.allclose(PBFactor().calculate(data).dropna(), 1.0 / data["pb"])
        assert np.allclose(PSFactor().calculate(data).dropna(), 1.0 / data["ps"])


class TestMomentumFactors:
    def test_momentum_20(self):
        data = _factor_data()
        factor = MomentumFactor(20)
        out = factor.calculate(data)
        assert factor.name == "momentum_20"
        expected = data["close"] / data["close"].shift(20) - 1.0
        assert np.allclose(out.dropna(), expected.dropna())

    def test_momentum_60_120(self):
        data = _factor_data()
        assert Momentum60Factor().name == "momentum_60"
        assert Momentum120Factor().name == "momentum_120"
        assert np.allclose(Momentum60Factor().calculate(data).dropna(),
                           (data["close"] / data["close"].shift(60) - 1.0).dropna())


class TestQualityFactors:
    def test_quality_passthrough(self):
        data = _factor_data()
        assert np.allclose(ROEFactor().calculate(data), data["roe"])
        assert np.allclose(ROICFactor().calculate(data), data["roic"])
        assert np.allclose(RevenueGrowthFactor().calculate(data), data["revenue_growth"])
        assert np.allclose(ProfitGrowthFactor().calculate(data), data["profit_growth"])


class TestVolatilityLiquidityFactors:
    def test_volatility(self):
        data = _factor_data()
        factor = VolatilityFactor(20)
        out = factor.calculate(data)
        assert factor.name == "volatility_20"
        returns = data["close"].pct_change()
        expected = returns.rolling(20).std() * (252 ** 0.5)
        assert np.allclose(out.dropna(), expected.dropna())

    def test_turnover_and_amount(self):
        data = _factor_data()
        assert np.allclose(TurnoverFactor().calculate(data), data["turnover"])
        expected = data["amount"].rolling(20).mean()
        assert np.allclose(Amount20Factor().calculate(data).dropna(), expected.dropna())


class TestFactoryAndRegistry:
    def test_default_factors_count(self):
        factors = FactorFactory.default_factors()
        assert len(factors) == 13
        assert all(isinstance(f, Factor) for f in factors)
        names = [f.name for f in factors]
        assert names == [
            "pe_inverse", "pb_inverse", "ps_inverse",
            "momentum_20", "momentum_60", "momentum_120",
            "roe", "roic", "revenue_growth", "profit_growth",
            "volatility_20", "turnover", "amount_20",
        ]

    def test_registry(self):
        reg = FactorRegistry()
        f = PEFactor()
        reg.register(f)
        assert reg.get("pe_inverse") is f
        assert reg.get("missing") is None
        assert reg.all() == [f]


# =====================================================================
# V3.8 - alpha metrics
# =====================================================================
class TestInformationCoefficient:
    def test_rank_ic_perfect_positive(self):
        factor = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
        forward = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
        ic = InformationCoefficient.rank_ic(factor, forward)
        assert ic == pytest.approx(1.0)

    def test_rank_ic_perfect_negative(self):
        factor = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
        forward = pd.Series([12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0])
        ic = InformationCoefficient.rank_ic(factor, forward)
        assert ic == pytest.approx(-1.0)

    def test_too_few_samples_zero(self):
        factor = pd.Series([1.0, 2.0, 3.0])
        forward = pd.Series([1.0, 2.0, 3.0])
        assert InformationCoefficient.rank_ic(factor, forward) == 0.0


class TestICIR:
    def test_too_few_zero(self):
        assert ICIRCalculator().calculate([1.0]) == 0.0

    def test_zero_std_zero(self):
        assert ICIRCalculator().calculate([0.0, 0.0, 0.0]) == 0.0

    def test_normal(self):
        assert ICIRCalculator().calculate([0.05, 0.06, 0.07]) == pytest.approx(0.06 / 0.01, rel=1e-6)


class TestQuantile:
    def test_analyze_monotonic(self):
        factor = pd.Series(np.arange(100, dtype=float))
        forward = pd.Series(np.arange(100, dtype=float) * 0.01)
        result = QuantileAnalyzer().analyze(factor, forward, quantiles=5)
        assert len(result) == 5
        vals = [result[k] for k in sorted(result)]
        assert vals == sorted(vals)

    def test_analyze_empty(self):
        assert QuantileAnalyzer().analyze(pd.Series([], dtype=float),
                                          pd.Series([], dtype=float)) == {}

    def test_long_short_spread_positive(self):
        factor = pd.Series(np.arange(100, dtype=float))
        forward = pd.Series(np.arange(100, dtype=float) * 0.01)
        spread = QuantileAnalyzer().long_short_spread(factor, forward, quantiles=5)
        assert spread > 0

    def test_long_short_empty_zero(self):
        assert QuantileAnalyzer().long_short_spread(
            pd.Series([], dtype=float), pd.Series([], dtype=float)) == 0.0


class TestDecay:
    def test_analyze_horizons(self):
        data = _factor_data(300)
        factor = MomentumFactor(20).calculate(data)
        result = FactorDecayAnalyzer().analyze(factor, data["close"],
                                               horizons=[1, 5, 20])
        assert set(result.keys()) == {1, 5, 20}
        assert all(isinstance(v, float) for v in result.values())

    def test_default_horizons(self):
        data = _factor_data(300)
        factor = MomentumFactor(20).calculate(data)
        result = FactorDecayAnalyzer().analyze(factor, data["close"])
        assert set(result.keys()) == {1, 3, 5, 10, 20}


class TestCorrelation:
    def test_calculate_returns_dataframe(self):
        data = _factor_data()
        frame = pd.DataFrame({
            "a": PEFactor().calculate(data),
            "b": PBFactor().calculate(data),
        })
        out = FactorCorrelation().calculate(frame)
        assert isinstance(out, pd.DataFrame)
        assert list(out.index) == ["a", "b"]
        assert out.loc["a", "a"] == pytest.approx(1.0)


class TestOrthogonalizer:
    def test_residual_orthogonal_to_control(self):
        data = _factor_data(200)
        target = data["pe"]
        controls = pd.DataFrame({"close": data["close"]})
        residual = Orthogonalizer().orthogonalize(target, controls)
        resid = residual.dropna()
        # residual must be uncorrelated with the control
        corr = resid.corr(controls.loc[resid.index, "close"])
        assert abs(corr) < 1e-8

    def test_empty_returns_nan(self):
        out = Orthogonalizer().orthogonalize(
            pd.Series([], dtype=float), pd.DataFrame({"x": []}))
        assert out.isna().all()


class TestAlphaScorer:
    def test_score_weights(self):
        scorer = AlphaScorer()
        assert scorer.score(mean_ic=1.0, icir=0.0, long_short=0.0, stability=0.0) == 30.0
        assert scorer.score(mean_ic=0.0, icir=1.0, long_short=0.0, stability=0.0) == 20.0
        assert scorer.score(mean_ic=0.0, icir=0.0, long_short=1.0, stability=0.0) == 30.0
        assert scorer.score(mean_ic=0.0, icir=0.0, long_short=0.0, stability=1.0) == 20.0

    def test_classify_bounds(self):
        scorer = AlphaScorer()
        assert scorer.classify(100) == "STRONG"
        assert scorer.classify(60) == "STRONG"
        assert scorer.classify(59) == "VALID"
        assert scorer.classify(35) == "VALID"
        assert scorer.classify(34) == "WEAK"
        assert scorer.classify(15) == "WEAK"
        assert scorer.classify(14) == "REJECT"


class TestFactorExperiment:
    def test_run_shape(self):
        data = _factor_data(300)
        factor = PEFactor().calculate(data)
        forward = data["close"].shift(-5) / data["close"] - 1
        result = FactorExperiment().run(factor, forward, ic_history=[])
        assert set(result.keys()) == {
            "ic", "mean_ic", "icir", "quantiles", "long_short",
            "stability", "score", "classification",
        }
        assert result["classification"] in {"STRONG", "VALID", "WEAK", "REJECT"}


class TestExperimentStore:
    def test_save_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ExperimentStore(os.path.join(tmp, "results"))
            path = store.save("test_run", {"ic": 0.1, "name": "中文"})
            assert os.path.exists(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["ic"] == 0.1
            assert data["name"] == "中文"
