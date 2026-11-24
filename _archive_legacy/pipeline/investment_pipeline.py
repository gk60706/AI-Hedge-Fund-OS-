"""V3.0.3 自动投资流水线：MarketData → Scanner → Committee → Portfolio → Risk → Report。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.investment_committee import (
    InvestmentCommitteeV29 as InvestmentCommittee,
)
from portfolio.portfolio_manager import (
    PortfolioManagerV30 as PortfolioManager,
)
from risk.risk_engine import (
    RiskEngineV30 as RiskEngine,
)
from scanner.market_scanner import (
    MarketScanner,
)


class InvestmentPipeline:
    def __init__(
        self,
        portfolio_value: float = 1_000_000,
    ):
        self.portfolio_value = portfolio_value
        self.scanner = MarketScanner()
        self.committee = InvestmentCommittee()
        self.portfolio_manager = PortfolioManager()
        self.risk_engine = RiskEngine()

    def run(self, scan_limit: int = 50) -> dict[str, Any]:
        candidates = self.scanner.run(scan_limit)
        decisions = []
        for stock in candidates:
            context = {
                "market_data": stock,
                "quant_signal": {
                    "score": 50,
                    "reasons": [
                        "等待真实量化因子",
                    ],
                },
                "macro": {
                    "score": 50,
                    "regime": "NEUTRAL",
                },
                "risk": {
                    "max_drawdown": -0.10,
                    "volatility": 0.03,
                },
            }
            result = self.committee.deliberate(context)
            committee = result["committee"]
            decisions.append({
                "code": stock["code"],
                "name": stock["name"],
                "decision": committee["decision"],
                "weighted_score": committee["weighted_score"],
                "analysis": result["agents"],
            })
        targets = self.portfolio_manager.build_targets(decisions)
        weights = {
            item["code"]: item["target_weight"]
            for item in targets
        }
        risk_result = self.risk_engine.validate_portfolio(weights)
        report = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "candidate_count": len(candidates),
            "decisions": decisions,
            "targets": targets,
            "risk": risk_result,
        }
        return report

    @staticmethod
    def save_report(
        report: dict[str, Any],
        directory: str = "reports",
    ) -> str:
        path = Path(directory)
        path.mkdir(
            parents=True,
            exist_ok=True,
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = path / f"daily_investment_{timestamp}.json"
        file_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return str(file_path)
