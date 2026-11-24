"""
AI Hedge Fund OS
V3.9.2 - AI Alpha Discovery Engine

Main Entry Point

研究流程：

    Data
      ↓
    Universe
      ↓
    Point-in-Time
      ↓
    Factor Processing
      ↓
    Alpha Search
      ↓
    Alpha Metrics
      ↓
    Deduplication
      ↓
    OOS Validation
      ↓
    Walk Forward
      ↓
    Backtest
      ↓
    Experiment Registry
      ↓
    Alpha Library

重要原则：

1. 不允许未来数据进入 Alpha 研究
2. 财务数据必须满足 PIT 约束
3. Alpha 指标必须由确定性引擎计算
4. LLM 不允许直接生成 IC / ICIR / 回测收益
5. 搜索阶段只能使用 Train 数据
6. Validation / OOS 数据不能参与 Alpha 搜索
7. A 股默认 Long Only
8. 研究结果不等同于真实交易结果
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np
import pandas as pd
import yaml

# ============================================================
# Project Root
# ============================================================
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ============================================================
# Internal Imports
# ============================================================
from data.panel import PanelData
from data.point_in_time import PITConfig, PointInTimeEngine
from data.akshare_client import AkShareClientV392
from factors.factory import FactorFactoryConfigV392, FactorFactoryV392
from factors.registry import FactorRegistryV392 as FactorRegistry
from alpha.search import AlphaSearchConfigV392, AlphaSearchEngineV392
from alpha.evaluator import AlphaEvaluator
from alpha.library import AlphaLibraryConfigV392, AlphaLibraryV392
from validation.audit import ResearchAuditConfigV392, ResearchAuditorV392
from validation.split import SplitConfigV392, TemporalDataSplitterV392
from validation.walk_forward import WalkForwardConfigV392, WalkForwardValidatorV392
from backtest.alpha_backtest import AlphaBacktestConfigV392, AlphaBacktestEngineV392
from backtest.costs import TransactionCostConfigV392
from backtest.returns import ForwardReturnConfigV392, ForwardReturnEngineV392
from experiments.registry import (
    AlphaMetadataV392,
    BacktestMetadataV392,
    DatasetMetadataV392,
    ExperimentRecordV392,
    ExperimentRegistryV392,
    OOSMetadataV392,
    ValidationMetadataV392,
    WalkForwardMetadataV392,
)

# ============================================================
# V392 Interface Adapters
#
# 说明：main_v392.py 是 V3.9.2 的总装配层蓝本（第 31 步）。
# ChatGPT 已预告第 32 步做「全项目接口对齐 + 第一次运行」。
# 以下适配层把蓝本中引用的接口映射到本地已融合的 V392 实现，
# 不改动任何已融合模块；接口深度对齐待第 32 步最终一致版本。
# ============================================================

class PointInTimeFilter:
    """V392 adapter: wrap PointInTimeEngine + PITConfig."""

    def __init__(
        self,
        strict: bool = True,
        require_available_date: bool = True,
    ):
        self._engine = PointInTimeEngine(
            config=PITConfig(
                strict=bool(strict),
                require_available_date=bool(require_available_date),
            )
        )

    def filter_panel(self, panel: PanelData) -> PanelData:
        df = self._engine.prepare(panel.to_dataframe())
        return PanelData.from_dataframe(df)


class HistoricalUniverse:
    """V392 adapter: dict-config universe filter on a panel."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}

    def filter_panel(self, panel: PanelData) -> PanelData:
        df = panel.to_dataframe()
        mask = pd.Series(True, index=df.index)
        if "is_tradeable" in df.columns:
            mask &= df["is_tradeable"].fillna(True).astype(bool)
        if "is_suspended" in df.columns:
            mask &= ~df["is_suspended"].fillna(False).astype(bool)
        if "is_st" in df.columns:
            mask &= ~df["is_st"].fillna(False).astype(bool)
        return PanelData.from_dataframe(df[mask].reset_index(drop=True))


class FactorFactory:
    """V392 adapter: dict-config FactorFactoryV392 (build -> factor matrix).

    中性化（industry / market_cap）仅在数据中存在对应列且配置启用时才开启；
    demo 面板无行业/市值列时自动关闭，避免因子构建失败。
    """

    def __init__(
        self,
        registry,
        config: Optional[Dict[str, Any]] = None,
        processing_config: Optional[Dict[str, Any]] = None,
    ):
        self._registry = registry
        self._config = config or {}
        self._processing_config = processing_config or {}
        self._factory = None

    def build(self, panel: PanelData) -> pd.DataFrame:
        cfg = self._config
        proc = self._processing_config
        tech = cfg.get("technical") or {}
        fund = cfg.get("fundamental") or {}
        winsorize = proc.get("winsorize") or {}
        df = panel.to_dataframe()
        ind_enabled = bool((proc.get("industry_neutralization") or {}).get("enabled", False))
        mcap_enabled = bool((proc.get("market_cap_neutralization") or {}).get("enabled", False))
        has_industry = "industry" in df.columns and df["industry"].notna().any()
        has_market_cap = "market_cap" in df.columns and df["market_cap"].notna().any()
        neutralize = (ind_enabled and has_industry) or (mcap_enabled and has_market_cap)
        neutralization_columns = []
        if ind_enabled and has_industry:
            neutralization_columns.append("industry")
        if mcap_enabled and has_market_cap:
            neutralization_columns.append("market_cap")
        if (ind_enabled and not has_industry) or (mcap_enabled and not has_market_cap):
            LOGGER.warning(
                "Neutralization enabled in config but columns missing/invalid; "
                "neutralization disabled for this panel."
            )
        self._factory = FactorFactoryV392(
            config=FactorFactoryConfigV392(
                include_technical=bool(tech.get("enabled", True)),
                include_fundamental=bool(fund.get("enabled", True)),
                winsorize=bool(winsorize.get("enabled", True)),
                winsor_method=str(winsorize.get("method", "mad")),
                neutralize=neutralize,
                neutralization_columns=neutralization_columns,
                fail_on_factor_error=False,
            )
        )
        return self._factory.build_matrix(df)


class _V392Generator:
    """V392 adapter: AlphaGenerator compatible with generate_candidates.

    本地 alpha/generator.AlphaGenerator 的 API 是
    generate(depth) / generate_population(size, max_depth)；
    这里包装为 generate(n=..., max_depth=..., max_nodes=..., features=...)。
    """

    def __init__(
        self,
        features: Optional[Sequence[str]] = None,
        seed: Optional[int] = None,
    ):
        self._features = list(features) if features else None
        self._seed = seed

    def generate(
        self,
        n: int = 100,
        max_depth: int = 3,
        max_nodes: int = 15,
        features: Optional[Sequence[str]] = None,
        **kwargs,
    ):
        if self._seed is not None:
            random.seed(self._seed)
        from alpha.generator import AlphaGenerator

        generator = AlphaGenerator()
        population = generator.generate_population(
            size=int(n),
            max_depth=int(max_depth),
        )
        if not population:
            raise ValueError("AlphaGenerator produced no expressions.")
        return population


class AlphaSearchEngine:
    """V392 adapter: dict-config AlphaSearchEngineV392 (search -> accepted list)."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        metrics_config: Optional[Dict[str, Any]] = None,
    ):
        cfg = config or {}
        mcfg = metrics_config or {}
        self._engine = AlphaSearchEngineV392(
            config=AlphaSearchConfigV392(
                n_candidates=int(cfg.get("candidates_per_round", 1000)),
                random_seed=int(cfg.get("random_seed", 392)),
                top_k=int(cfg.get("rounds", 20)),
                max_depth=int(cfg.get("max_depth", 4)),
                max_nodes=int(cfg.get("max_nodes", 15)),
                min_obs=int(mcfg.get("min_cross_section_size", 100)),
                min_abs_ic=float(mcfg.get("min_ic", 0.02)),
                min_abs_icir=float(mcfg.get("min_icir", 0.30)),
                min_abs_spread=float(mcfg.get("min_quantile_spread", 0.005)),
                complexity_penalty_weight=float(
                    (config or {}).get("complexity", {}).get("node_penalty", 0.002)
                    if config else 0.002
                ),
            ),
            generator=_V392Generator(
                features=list(cfg.get("features", [])),
                seed=int(cfg.get("random_seed", 392)),
            ),
            evaluator=AlphaEvaluator(),
        )

    def search(self, factors: pd.DataFrame, panel: PanelData):
        # search data = 面板 + 因子矩阵（剥 __processed 后缀）+ forward_return
        data = panel.to_dataframe()
        matrix = factors
        keep = [c for c in matrix.columns if c.endswith("__processed")]
        renamed = {c: c[: -len("__processed")] for c in keep}
        if keep:
            # 面板原始列与因子列同名时，因子列优先（删除面板同名列避免 _x/_y 后缀）
            overlap = [c for c in renamed.values() if c in data.columns]
            if overlap:
                data = data.drop(columns=overlap)
            data = data.merge(
                matrix[["date", "code"] + keep].rename(columns=renamed),
                on=["date", "code"],
                how="left",
            )
        data = _attach_forward_return_v392(data, horizon=5)
        result = self._engine.search(
            data=data,
            factors=list(renamed.values()),
        )
        return result.accepted


class AlphaLibrary:
    """V392 adapter: path/max_size config AlphaLibraryV392."""

    def __init__(self, path: str, max_size: Optional[int] = None):
        self._lib = AlphaLibraryV392(
            config=AlphaLibraryConfigV392(
                path=str(path),
                max_size=int(max_size) if max_size is not None else None,
                auto_save=True,
            )
        )

    def add(self, alpha) -> None:
        self._lib.add_candidate(alpha)


class ValidationAudit:
    """V392 adapter: wrap ResearchAuditorV392."""

    def __init__(self, strict: bool = True):
        self._auditor = ResearchAuditorV392(
            config=ResearchAuditConfigV392(strict=bool(strict))
        )

    def run(self, df: pd.DataFrame):
        return self._auditor.audit(df)


class SplitConfig:
    """V392 adapter: ratio-based split config (converted to periods at split time)."""

    def __init__(
        self,
        train_ratio: float = 0.6,
        validation_ratio: float = 0.2,
        test_ratio: float = 0.2,
        purge_days: int = 0,
        embargo_days: int = 0,
    ):
        self.train_ratio = float(train_ratio)
        self.validation_ratio = float(validation_ratio)
        self.test_ratio = float(test_ratio)
        self.purge_days = int(purge_days)
        self.embargo_days = int(embargo_days)


class TemporalDataSplitter:
    """V392 adapter: wrap TemporalDataSplitterV392, ratios -> periods."""

    def __init__(self, split_config: Optional[SplitConfig] = None):
        self._split_config = split_config

    def split(self, df: pd.DataFrame):
        if self._split_config is None:
            return []
        dates = pd.DatetimeIndex(sorted(pd.to_datetime(df["date"]).unique()))
        total = max(len(dates) - 1, 1)
        train = max(int(total * self._split_config.train_ratio), 1)
        valid = max(int(total * self._split_config.validation_ratio), 1)
        test = max(total - train - valid, 1)
        real = SplitConfigV392(
            min_train_periods=train,
            validation_periods=valid,
            test_periods=test,
            step_periods=max(int(total * 0.1), 1),
            purge_periods=self._split_config.purge_days,
            embargo_periods=self._split_config.embargo_days,
            label_horizon=0,
        )
        return TemporalDataSplitterV392(config=real).split_all(df)


def _evaluate_signal_v392(df: pd.DataFrame, alpha) -> pd.Series:
    """Evaluate an alpha object into a signal column (V392 adapter)."""
    engine = AlphaSearchEngineV392(
        evaluator=AlphaEvaluator(),
        generator=_V392Generator(),
    )
    expr = getattr(alpha, "expression", None)
    if expr is not None:
        return engine.evaluate_expression(expr, df)
    expr_str = getattr(alpha, "expression_string", None)
    if expr_str and expr_str in df.columns:
        return df[expr_str].astype(float)
    raise ValueError(
        f"Cannot evaluate signal for alpha: {getattr(alpha, 'alpha_id', '?')}"
    )


def _attach_forward_return_v392(df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """Attach forward_return column via ForwardReturnEngineV392 (V392 adapter)."""
    result = ForwardReturnEngineV392(
        config=ForwardReturnConfigV392(horizon=int(horizon))
    ).calculate(df)
    return result.data


class WalkForwardValidator:
    """V392 adapter: day-based config WalkForwardValidatorV392."""

    def __init__(
        self,
        train_days: int = 504,
        validation_days: int = 126,
        test_days: int = 126,
        step_days: int = 63,
        purge_days: int = 5,
        embargo_days: int = 5,
    ):
        self._validator = WalkForwardValidatorV392(
            config=WalkForwardConfigV392(
                split_config=SplitConfigV392(
                    min_train_periods=int(train_days),
                    validation_periods=int(validation_days),
                    test_periods=int(test_days),
                    step_periods=int(step_days),
                    purge_periods=int(purge_days),
                    embargo_periods=int(embargo_days),
                    label_horizon=0,
                )
            )
        )

    def validate(self, alpha, panel):
        df = panel.to_dataframe()
        df["signal"] = _evaluate_signal_v392(df, alpha)
        df = _attach_forward_return_v392(df)
        return self._validator.run(
            df,
            signal_column="signal",
            return_column="forward_return",
            alpha_id=getattr(alpha, "alpha_id", None),
        )


class AlphaBacktester:
    """V392 adapter: dict-config AlphaBacktestEngineV392."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cost_config: Optional[Dict[str, Any]] = None,
    ):
        cfg = config or {}
        cost = cost_config or {}
        commission = cost.get("commission") or {}
        stamp = cost.get("stamp_duty") or {}
        slippage = cost.get("slippage") or {}
        self.horizon = 5
        self._engine = AlphaBacktestEngineV392(
            config=AlphaBacktestConfigV392(
                horizon=self.horizon,
                long_only=str(cfg.get("mode", "long_only")) == "long_only",
                quantiles=5,
                min_cross_section=int(cfg.get("portfolio_size", 20)),
                transaction_cost=TransactionCostConfigV392(
                    commission_rate=float(commission.get("rate", 0.0003)),
                    min_commission=float(commission.get("min_fee", 0.0)),
                    stamp_duty_rate=float(stamp.get("sell_rate", 0.0005)),
                    slippage_rate=float(slippage.get("buy", 0.0005)),
                ),
            )
        )

    def run(self, alpha, panel):
        df = panel.to_dataframe()
        df["signal"] = _evaluate_signal_v392(df, alpha)
        df = _attach_forward_return_v392(df, horizon=self.horizon)
        return self._engine.run(df)


class ExperimentRecord:
    """V392 adapter: lightweight record consumed by ExperimentRegistry.create."""

    def __init__(
        self,
        experiment_id: str = "",
        status: str = "",
        created_at: str = "",
        updated_at: str = "",
        project: str = "",
        version: str = "",
    ):
        self.experiment_id = str(experiment_id)
        self.status = str(status)
        self.created_at = str(created_at)
        self.updated_at = str(updated_at)
        self.project = str(project)
        self.version = str(version)


class ExperimentRegistry:
    """V392 adapter: wrap ExperimentRegistryV392 with create(record) semantics."""

    def __init__(self, path: str = "experiments/registry.json"):
        self._reg = ExperimentRegistryV392(path=str(path))

    def create(self, record: ExperimentRecord) -> None:
        full = ExperimentRecordV392(
            experiment_id=record.experiment_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            status=record.status,
            project_version=record.version,
            git_commit="",
            python_version=sys.version.split()[0],
            platform=sys.platform,
            random_seed=None,
            dataset=DatasetMetadataV392(),
            alpha=AlphaMetadataV392(),
            validation=ValidationMetadataV392(),
            backtest=BacktestMetadataV392(),
            oos=OOSMetadataV392(),
            walk_forward=WalkForwardMetadataV392(),
            parameters={},
            search_space={},
            environment={},
            config_hash="",
        )
        self._reg.save(full)


class AkShareClient:
    """V392 adapter: dict-config AkShareClientV392.

    注意：整市场面板加载（markets -> codes）属第 32 步接口对齐范围；
    请优先使用 data.local_file 配置本地面板。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._client = AkShareClientV392()

    def load_market_panel(
        self,
        start_date: str,
        end_date: str,
        markets,
    ) -> PanelData:
        LOGGER.warning(
            "AkShare 整市场面板加载（markets->codes）待第 32 步接口对齐，"
            "建议配置 data.local_file 使用本地面板。"
        )
        return self._client.get_panel(
            codes=[],
            start_date=start_date,
            end_date=end_date,
            skip_errors=True,
        )


# ============================================================
# Logging
# ============================================================
LOGGER = logging.getLogger("AI_Hedge_Fund_OS.V3.9.2")


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Configure console + file logging.
    """
    logging_config = config.get("logging", {})
    level_name = str(logging_config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    LOGGER.setLevel(level)
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # 避免重复添加 Handler
    if LOGGER.handlers:
        return
    console_enabled = logging_config.get("console", True)
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        LOGGER.addHandler(console_handler)
    file_path = logging_config.get("file")
    if file_path:
        file_path = ROOT_DIR / file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)


# ============================================================
# Configuration
# ============================================================
def load_config(
    config_path: str = "configs/v392.yaml",
) -> Dict[str, Any]:
    path = ROOT_DIR / config_path
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a YAML mapping.")
    return config


# ============================================================
# Random Seed
# ============================================================
def set_random_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


# ============================================================
# Utility
# ============================================================
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def json_safe(value: Any) -> Any:
    """
    Convert numpy / pandas objects to JSON-safe values.
    """
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


# ============================================================
# Runtime Context
# ============================================================
class V392Context:
    """
    Runtime context for one V3.9.2 experiment.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.started_at = utc_now_iso()
        self.experiment_id: Optional[str] = None
        self.panel: Optional[PanelData] = None
        self.factors: Optional[pd.DataFrame] = None
        self.alphas = []
        self.oos_results = []
        self.walk_forward_results = []
        self.backtest_results = []
        self.errors = []

    def add_error(self, message: str) -> None:
        self.errors.append(
            {
                "timestamp": utc_now_iso(),
                "message": str(message),
            }
        )


# ============================================================
# Configuration Validation
# ============================================================
def validate_config(config: Dict[str, Any]) -> None:
    required_sections = [
        "project",
        "data",
        "universe",
        "point_in_time",
        "factors",
        "alpha_search",
        "alpha_metrics",
        "backtest",
        "oos",
        "walk_forward",
        "experiments",
    ]
    missing = [section for section in required_sections if section not in config]
    if missing:
        raise ValueError(
            "Missing configuration sections: " + ", ".join(missing)
        )
    data_config = config["data"]
    start_date = pd.Timestamp(data_config["start_date"])
    end_date = pd.Timestamp(data_config["end_date"])
    if start_date >= end_date:
        raise ValueError(
            "data.start_date must be earlier "
            "than data.end_date."
        )
    search_config = config["alpha_search"]
    if int(search_config["max_depth"]) < 1:
        raise ValueError("alpha_search.max_depth must be >= 1.")
    if int(search_config["max_nodes"]) < 1:
        raise ValueError("alpha_search.max_nodes must be >= 1.")
    oos_config = config["oos"]
    ratio_sum = (
        float(oos_config["train_ratio"])
        + float(oos_config["validation_ratio"])
        + float(oos_config["test_ratio"])
    )
    if abs(ratio_sum - 1.0) > 1e-8:
        raise ValueError(
            "OOS train/validation/test ratios "
            "must sum to 1.0."
        )


# ============================================================
# Experiment ID
# ============================================================
def create_experiment_id(config: Dict[str, Any]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    seed = config["alpha_search"].get("random_seed", 392)
    return (
        f"V392_"
        f"{timestamp}_"
        f"seed{seed}"
    )


# ============================================================
# Data Loading
# ============================================================
def load_panel(config: Dict[str, Any]) -> PanelData:
    """
    Load research panel.

    当前支持：

    1. 本地 CSV
    2. AkShare

    优先使用配置中的本地文件，
    便于先完成整个系统集成测试。
    """
    data_config = config["data"]
    local_file = data_config.get("local_file")
    if local_file:
        path = ROOT_DIR / local_file
        if not path.exists():
            raise FileNotFoundError(f"Local panel file not found: {path}")
        LOGGER.info("Loading local panel: %s", path)
        df = pd.read_csv(path)
        return PanelData.from_dataframe(df)
    LOGGER.info("No local panel configured. Using AkShare client.")
    from data.akshare_client import AkShareClientV392

    client = AkShareClient(config=data_config)
    start_date = data_config["start_date"]
    end_date = data_config["end_date"]
    universe = config["universe"]
    markets = universe.get("markets", ["SH", "SZ", "BJ"])
    panel = client.load_market_panel(
        start_date=start_date,
        end_date=end_date,
        markets=markets,
    )
    return panel


# ============================================================
# Historical Universe
# ============================================================
def apply_universe_filter(
    panel: PanelData,
    config: Dict[str, Any],
) -> PanelData:
    """
    Apply historical universe rules.

    注意：

    如果生命周期字段缺失，
    HistoricalUniverse 应明确报告缺失，
    而不是默认为所有股票一直存在。
    """
    universe_config = config["universe"]
    try:
        universe = HistoricalUniverse(config=universe_config)
        return universe.filter_panel(panel)
    except Exception as exc:
        LOGGER.warning(
            "Historical universe filter "
            "could not be fully applied: %s",
            exc,
        )
        # 严格研究模式下直接失败
        if config["audit"].get("strict", True):
            raise
        return panel


# ============================================================
# PIT Filter
# ============================================================
def apply_pit_filter(
    panel: PanelData,
    config: Dict[str, Any],
) -> PanelData:
    pit_config = config["point_in_time"]
    if not pit_config.get("enabled", True):
        LOGGER.warning("PIT filtering is disabled.")
        return panel
    pit_filter = PointInTimeFilter(
        strict=pit_config.get("strict", True),
        require_available_date=pit_config.get("require_available_date", True),
    )
    return pit_filter.filter_panel(panel)


# ============================================================
# Factor Engine
# ============================================================
def build_factors(
    panel: PanelData,
    config: Dict[str, Any],
) -> pd.DataFrame:
    """
    Build factor matrix.

    FactorFactory is responsible for:

    - technical factors
    - fundamental factors
    - transforms
    - neutralization
    """
    factor_config = config["factors"]
    processing_config = config["factor_processing"]
    registry = FactorRegistry()
    factory = FactorFactory(
        registry=registry,
        config=factor_config,
        processing_config=processing_config,
    )
    LOGGER.info("Building factor matrix...")
    factor_df = factory.build(panel)
    if factor_df.empty:
        raise ValueError("Factor engine returned empty DataFrame.")
    LOGGER.info("Factor matrix shape: %s", factor_df.shape)
    return factor_df


# ============================================================
# Data Split
# ============================================================
def split_data(
    panel: PanelData,
    config: Dict[str, Any],
):
    oos_config = config["oos"]
    split_config = SplitConfig(
        train_ratio=float(oos_config["train_ratio"]),
        validation_ratio=float(oos_config["validation_ratio"]),
        test_ratio=float(oos_config["test_ratio"]),
        purge_days=int(
            config["walk_forward"].get("purge_days", 0)
        ),
        embargo_days=int(
            config["walk_forward"].get("embargo_days", 0)
        ),
    )
    splitter = TemporalDataSplitter(split_config)
    return splitter.split(panel.to_dataframe())


# ============================================================
# Alpha Search
# ============================================================
def run_alpha_search(
    factors: pd.DataFrame,
    panel: PanelData,
    config: Dict[str, Any],
):
    search_config = config["alpha_search"]
    metrics_config = config["alpha_metrics"]
    LOGGER.info("Starting Alpha Search...")
    engine = AlphaSearchEngine(
        config=search_config,
        metrics_config=metrics_config,
    )
    results = engine.search(
        factors=factors,
        panel=panel,
    )
    LOGGER.info(
        "Alpha search completed. Candidates=%d",
        len(results),
    )
    return results


# ============================================================
# Alpha Library
# ============================================================
def load_alpha_library(
    config: Dict[str, Any],
) -> AlphaLibrary:
    library_config = config["alpha_library"]
    path = ROOT_DIR / library_config["path"]
    ensure_directory(path.parent)
    return AlphaLibrary(
        path=str(path),
        max_size=int(
            library_config.get("max_alpha_count", 500)
        ),
    )


def _ic_v392(s: pd.Series, t: pd.Series) -> float:
    """Rank IC between signal and target (V392 adapter)."""
    z = pd.concat([s, t], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(z) < 3:
        return float("nan")
    return float(z.iloc[:, 0].rank().corr(z.iloc[:, 1].rank()))


def _evaluate_alpha_oos_v392(
    alpha,
    df: pd.DataFrame,
    min_ic: float = 0.02,
    min_train_retention: float = 0.30,
    target_col: str = "forward_return",
) -> Any:
    """V392 OOS 评估：用 _evaluate_signal_v392 求信号（兼容 AlphaCandidateV392）。"""
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"])
    if target_col not in x.columns:
        x = _attach_forward_return_v392(x, horizon=5)
        target_col = "forward_return"
    dates = pd.Index(sorted(x["date"].unique()))
    n = len(dates)
    tr = int(n * 0.6)
    te = int(n * 0.8)

    def ev(sub: pd.DataFrame) -> float:
        z = sub.copy()
        z["signal"] = _evaluate_signal_v392(z, alpha)
        vals = []
        for _, d in z.groupby("date"):
            v = _ic_v392(d["signal"], d[target_col])
            if pd.notna(v):
                vals.append(v)
        return float(np.mean(vals)) if vals else float("nan")

    train_ic = ev(x[x["date"].isin(dates[:tr])])
    oos_ic = ev(x[x["date"].isin(dates[te:])])
    passed = (
        pd.notna(oos_ic)
        and abs(oos_ic) >= min_ic
        and (pd.isna(train_ic) or abs(oos_ic) >= min_train_retention * abs(train_ic))
    )
    return type(
        "OOSResult",
        (),
        {
            "alpha": alpha,
            "train_ic": train_ic,
            "oos_ic": oos_ic,
            "passed": bool(passed),
        },
    )()


# ============================================================
# OOS Validation
# ============================================================
def run_oos_validation(
    alphas,
    panel: PanelData,
    config: Dict[str, Any],
):
    """
    Run untouched OOS validation.

    Search results must NOT use test data.
    """
    oos_config = config["oos"]
    results = []
    for alpha in alphas:
        try:
            result = _evaluate_alpha_oos_v392(
                alpha=alpha,
                df=panel.to_dataframe(),
                min_ic=float(oos_config["min_ic"]),
                min_train_retention=float(oos_config["min_train_retention"]),
            )
            results.append(result)
        except Exception as exc:
            LOGGER.exception(
                "OOS validation failed for alpha: %s",
                exc,
            )
    LOGGER.info(
        "OOS validation completed: %d results",
        len(results),
    )
    return results


# ============================================================
# Walk Forward
# ============================================================
def run_walk_forward(
    alphas,
    panel: PanelData,
    config: Dict[str, Any],
):
    wf_config = config["walk_forward"]
    validator = WalkForwardValidator(
        train_days=int(wf_config["train_days"]),
        validation_days=int(wf_config["validation_days"]),
        test_days=int(wf_config["test_days"]),
        step_days=int(wf_config["step_days"]),
        purge_days=int(wf_config["purge_days"]),
        embargo_days=int(wf_config["embargo_days"]),
    )
    results = []
    for alpha in alphas:
        try:
            result = validator.validate(
                alpha=alpha,
                panel=panel,
            )
            results.append(result)
        except Exception as exc:
            LOGGER.exception(
                "Walk-forward failed: %s",
                exc,
            )
    LOGGER.info(
        "Walk-forward completed: %d results",
        len(results),
    )
    return results


# ============================================================
# Backtest
# ============================================================
def run_backtest(
    alphas,
    panel: PanelData,
    config: Dict[str, Any],
):
    backtest_config = config["backtest"]
    cost_config = config["transaction_cost"]
    backtester = AlphaBacktester(
        config=backtest_config,
        cost_config=cost_config,
    )
    results = []
    for alpha in alphas:
        try:
            result = backtester.run(
                alpha=alpha,
                panel=panel,
            )
            results.append(result)
        except Exception as exc:
            LOGGER.exception(
                "Backtest failed: %s",
                exc,
            )
    LOGGER.info(
        "Backtest completed: %d results",
        len(results),
    )
    return results


# ============================================================
# Validation Audit
# ============================================================
def run_audit(
    panel: PanelData,
    config: Dict[str, Any],
):
    audit_config = config["audit"]
    if not audit_config.get("enabled", True):
        LOGGER.info("Validation audit disabled.")
        return None
    LOGGER.info("Running validation audit...")
    auditor = ValidationAudit(
        strict=audit_config.get("strict", True)
    )
    result = auditor.run(panel.to_dataframe())
    if hasattr(result, "passed"):
        if not result.passed:
            raise ValueError("Validation audit failed.")
    LOGGER.info("Validation audit completed.")
    return result


# ============================================================
# Experiment Registry
# ============================================================
def load_registry(
    config: Dict[str, Any],
) -> ExperimentRegistry:
    experiment_config = config["experiments"]
    path = ROOT_DIR / experiment_config["path"]
    ensure_directory(path.parent)
    return ExperimentRegistry(path=str(path))


# ============================================================
# Save Experiment Summary
# ============================================================
def save_summary(context: V392Context) -> Path:
    output_dir = ROOT_DIR / "experiments"
    ensure_directory(output_dir)
    path = (
        output_dir
        / f"{context.experiment_id}_summary.json"
    )
    summary = {
        "project": context.config["project"],
        "experiment_id": context.experiment_id,
        "started_at": context.started_at,
        "finished_at": utc_now_iso(),
        "panel_shape": (
            context.panel.to_dataframe().shape
            if context.panel is not None
            else None
        ),
        "factor_shape": (
            context.factors.shape
            if context.factors is not None
            else None
        ),
        "alpha_count": len(context.alphas),
        "oos_count": len(context.oos_results),
        "walk_forward_count": len(context.walk_forward_results),
        "backtest_count": len(context.backtest_results),
        "errors": context.errors,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(json_safe(summary), f, ensure_ascii=False, indent=2)
    return path


def _build_research_data_v392(
    panel: PanelData,
    factors: pd.DataFrame,
) -> PanelData:
    """面板 + 因子矩阵（剥 __processed 后缀）→ 供 OOS/WF/BT 阶段 evaluate 使用。"""
    data = panel.to_dataframe()
    keep = [c for c in factors.columns if c.endswith("__processed")]
    renamed = {c: c[: -len("__processed")] for c in keep}
    if keep:
        overlap = [c for c in renamed.values() if c in data.columns]
        if overlap:
            data = data.drop(columns=overlap)
        data = data.merge(
            factors[["date", "code"] + keep].rename(columns=renamed),
            on=["date", "code"],
            how="left",
        )
    return PanelData.from_dataframe(data)


# ============================================================
# Main Pipeline
# ============================================================
def run_pipeline(config: Dict[str, Any]) -> V392Context:
    context = V392Context(config)
    context.experiment_id = create_experiment_id(config)
    LOGGER.info("=" * 70)
    LOGGER.info("AI Hedge Fund OS V3.9.2")
    LOGGER.info("Experiment: %s", context.experiment_id)
    LOGGER.info("=" * 70)
    # --------------------------------------------------------
    # Step 1 - Data
    # --------------------------------------------------------
    LOGGER.info("[1/10] Loading market panel...")
    panel = load_panel(config)
    context.panel = panel
    LOGGER.info("Panel loaded: %s", panel.to_dataframe().shape)
    # --------------------------------------------------------
    # Step 2 - Historical Universe
    # --------------------------------------------------------
    LOGGER.info("[2/10] Applying historical universe...")
    panel = apply_universe_filter(panel, config)
    context.panel = panel
    # --------------------------------------------------------
    # Step 3 - PIT
    # --------------------------------------------------------
    LOGGER.info("[3/10] Applying Point-in-Time filter...")
    panel = apply_pit_filter(panel, config)
    context.panel = panel
    # --------------------------------------------------------
    # Step 4 - Audit
    # --------------------------------------------------------
    LOGGER.info("[4/10] Running data audit...")
    run_audit(panel, config)
    # --------------------------------------------------------
    # Step 5 - Factors
    # --------------------------------------------------------
    LOGGER.info("[5/10] Building factors...")
    factors = build_factors(panel, config)
    context.factors = factors
    research_data = _build_research_data_v392(panel, factors)
    # --------------------------------------------------------
    # Step 6 - Alpha Search
    # --------------------------------------------------------
    LOGGER.info("[6/10] Searching Alpha...")
    alpha_results = run_alpha_search(factors, panel, config)
    context.alphas = alpha_results
    if not alpha_results:
        raise RuntimeError("Alpha search returned no candidates.")
    # --------------------------------------------------------
    # Step 7 - OOS
    # --------------------------------------------------------
    LOGGER.info("[7/10] Running OOS validation...")
    oos_results = run_oos_validation(alpha_results, research_data, config)
    context.oos_results = oos_results
    # --------------------------------------------------------
    # Step 8 - Walk Forward
    # --------------------------------------------------------
    LOGGER.info("[8/10] Running Walk Forward...")
    wf_results = run_walk_forward(alpha_results, research_data, config)
    context.walk_forward_results = (wf_results)
    # --------------------------------------------------------
    # Step 9 - Backtest
    # --------------------------------------------------------
    LOGGER.info("[9/10] Running Alpha backtest...")
    backtest_results = run_backtest(alpha_results, research_data, config)
    context.backtest_results = (backtest_results)
    # --------------------------------------------------------
    # Step 10 - Library + Registry
    # --------------------------------------------------------
    LOGGER.info("[10/10] Persisting Alpha Library...")
    library = load_alpha_library(config)
    registry = load_registry(config)
    # 保存通过 OOS 的 Alpha
    oos_only = config["alpha_library"].get("save_oos_only", True)
    if oos_only:
        passed_alphas = []
        for result in oos_results:
            passed = getattr(result, "passed", False)
            if passed:
                alpha = getattr(result, "alpha", None)
                if alpha is not None:
                    passed_alphas.append(alpha)
    else:
        passed_alphas = alpha_results
    for alpha in passed_alphas:
        try:
            library.add(alpha)
        except Exception as exc:
            LOGGER.warning(
                "Failed to save alpha: %s",
                exc,
            )
    # --------------------------------------------------------
    # Experiment Registry
    # --------------------------------------------------------
    try:
        record = ExperimentRecord(
            experiment_id=context.experiment_id,
            status="completed",
            created_at=context.started_at,
            updated_at=utc_now_iso(),
            project=config["project"].get("name", "AI Hedge Fund OS"),
            version=config["project"].get("version", "3.9.2"),
        )
        registry.create(record)
    except Exception as exc:
        LOGGER.warning(
            "Experiment registry persistence failed: %s",
            exc,
        )
    summary_path = save_summary(context)
    LOGGER.info("=" * 70)
    LOGGER.info("V3.9.2 pipeline completed.")
    LOGGER.info("Alpha candidates: %d", len(context.alphas))
    LOGGER.info("OOS results: %d", len(context.oos_results))
    LOGGER.info("Walk Forward results: %d", len(context.walk_forward_results))
    LOGGER.info("Backtest results: %d", len(context.backtest_results))
    LOGGER.info("Summary: %s", summary_path)
    LOGGER.info("=" * 70)
    return context


# ============================================================
# Demo Data
# ============================================================
def generate_demo_panel(
    n_days: int = 600,
    n_stocks: int = 300,
    seed: int = 392,
) -> pd.DataFrame:
    """
    Generate synthetic cross-sectional data.

    ONLY for integration testing.

    Never use demo data to make investment conclusions.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-01", periods=n_days)
    codes = [
        f"{600000 + i:06d}"
        for i in range(n_stocks)
    ]
    rows = []
    for date in dates:
        returns = rng.normal(0, 0.02, n_stocks)
        close = (
            10
            * np.exp(np.cumsum(returns))
        )
        volume = rng.lognormal(
            mean=12,
            sigma=0.8,
            size=n_stocks,
        )
        amount = (volume * close)
        pe = rng.lognormal(
            mean=2.5,
            sigma=0.8,
            size=n_stocks,
        )
        pb = rng.lognormal(
            mean=0.5,
            sigma=0.6,
            size=n_stocks,
        )
        roe = rng.normal(0.10, 0.08, n_stocks)
        momentum_20 = (returns + rng.normal(0, 0.01, n_stocks))
        revenue_growth = rng.normal(0.10, 0.15, n_stocks)
        profit_growth = rng.normal(0.12, 0.20, n_stocks)
        for i, code in enumerate(codes):
            c = close[i]
            o = c * (1 + rng.normal(0, 0.005))
            hi = max(o, c) * (1 + abs(rng.normal(0, 0.002)))
            lo = min(o, c) * (1 - abs(rng.normal(0, 0.002)))
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "open": o,
                    "high": hi,
                    "low": lo,
                    "close": c,
                    "volume": volume[i],
                    "amount": amount[i],
                    "turnover": rng.uniform(0.01, 0.08),
                    "pe": pe[i],
                    "pb": pb[i],
                    "roe": roe[i],
                    "roic": (roe[i] + rng.normal(0, 0.02)),
                    "revenue_growth": revenue_growth[i],
                    "profit_growth": profit_growth[i],
                    "available_date": date,
                    "is_tradeable": True,
                    "limit_up": False,
                    "limit_down": False,
                }
            )
    return pd.DataFrame(rows)


def run_demo(config: Dict[str, Any]) -> None:
    LOGGER.info("Running V3.9.2 synthetic demo.")
    df = generate_demo_panel()
    demo_path = (ROOT_DIR / "data" / "demo_panel_v392.csv")
    ensure_directory(demo_path.parent)
    df.to_csv(demo_path, index=False)
    config = dict(config)
    config["data"] = dict(config["data"])
    config["data"]["local_file"] = str(
        demo_path.relative_to(ROOT_DIR)
    )
    run_pipeline(config)


# ============================================================
# CLI
# ============================================================
def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "AI Hedge Fund OS V3.9.2 Alpha Discovery Engine"
        )
    )
    parser.add_argument(
        "--config",
        default="configs/v392.yaml",
        help="Path to YAML configuration.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run synthetic integration demo.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override random seed.",
    )
    return parser


# ============================================================
# CLI Main
# ============================================================
def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        validate_config(config)
        seed = (
            args.seed
            if args.seed is not None
            else int(
                config["alpha_search"].get("random_seed", 392)
            )
        )
        set_random_seed(seed)
        setup_logging(config)
        LOGGER.info("Random seed: %d", seed)
        if args.demo:
            run_demo(config)
        else:
            run_pipeline(config)
        return 0
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted by user.")
        return 130
    except Exception as exc:
        LOGGER.exception(
            "V3.9.2 pipeline failed: %s",
            exc,
        )
        return 1


# ============================================================
# Entry
# ============================================================
if __name__ == "__main__":
    raise SystemExit(main())
