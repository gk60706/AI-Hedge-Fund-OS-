"""V3.9.1 unified research pipeline (dump verbatim; AlphaLibraryV391 aliased)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from alpha.library import AlphaLibraryV391 as AlphaLibrary
from alpha.scorer import robust_score
from alpha.search import AlphaSearch
from backtest.dataset import prepare_dataset
from backtest.metrics import performance_metrics
from backtest.portfolio import top_quantile_portfolio
from validation.audit import full_audit
from validation.oos import evaluate_oos


@dataclass
class ResearchResult:
    champion: dict
    audit: dict
    backtest_metrics: dict
    candidates: list[dict]


class ResearchPipeline:
    def __init__(self, seed: int = 42, alpha_library=None):
        self.seed = seed
        self.alpha_library = alpha_library or AlphaLibrary()

    def run(
        self,
        panel: pd.DataFrame,
        train_end: str,
        oos_start: str,
        n_candidates: int = 300,
        horizon: int = 1,
    ) -> ResearchResult:
        # 1. 数据标准化
        panel = prepare_dataset(panel)
        # 2. 数据审计
        audit = full_audit(panel)
        # 3. Train / OOS
        train = panel[panel["date"] <= pd.Timestamp(train_end)].copy()
        oos = panel[panel["date"] >= pd.Timestamp(oos_start)].copy()
        if train.empty:
            raise ValueError("Train 数据为空")
        if oos.empty:
            raise ValueError("OOS 数据为空")
        # 4. Alpha Search
        search = AlphaSearch(
            seed=self.seed,
            max_depth=3,
            correlation_threshold=0.90,
        )
        candidates = search.search(
            train=train,
            n_candidates=n_candidates,
            horizon=horizon,
        )
        if not candidates:
            raise RuntimeError("没有产生有效 Alpha")
        # 5. OOS Validation
        scored = []
        for candidate in candidates[:100]:
            oos_result = evaluate_oos(
                candidate["expression"],
                oos,
                horizon=horizon,
            )
            result = dict(candidate)
            result.update(oos_result)
            result["robust_score"] = robust_score(
                ic=result["ic"],
                icir=result["icir"],
                qspread=result["q5_q1"],
                positive_ratio=result["positive_ic_ratio"],
                oos_ic=result["oos_ic"],
                turnover=0.0,
                complexity=result["complexity"],
            )
            scored.append(result)
        if not scored:
            raise RuntimeError("OOS 没有有效 Alpha")
        # 6. Champion
        scored.sort(key=lambda x: x["robust_score"], reverse=True)
        champion = scored[0]
        # 7. Full Period Backtest
        signal = search.evaluator.evaluate(champion["expression"], panel)
        equity, trades = top_quantile_portfolio(
            panel=panel,
            signal=signal,
            quantile=0.80,
            initial_cash=1_000_000,
        )
        metrics = performance_metrics(equity)
        # 8. Alpha Library
        self.alpha_library.save(scored[:20])
        return ResearchResult(
            champion=champion,
            audit=audit,
            backtest_metrics=metrics,
            candidates=scored,
        )
