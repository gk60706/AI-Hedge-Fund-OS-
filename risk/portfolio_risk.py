"""V3.1 组合风险：组合波动率 / 集中度 / 风险等级。"""

from __future__ import annotations

from typing import Any


class PortfolioRisk:
    """组合风险分析。"""

    def analyze(
        self,
        positions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """分析组合风险。

        Args:
            positions: 持仓列表（每项含 weight / volatility）。

        Returns:
            {"portfolio_volatility", "concentration", "risk_level"}。
        """
        total = sum(
            float(p.get("weight", 0.0))
            for p in positions
        )
        if total <= 0:
            return {
                "portfolio_volatility": 0.0,
                "concentration": 0.0,
                "risk_level": "LOW",
            }
        weights = [
            float(p.get("weight", 0.0)) / total
            for p in positions
        ]
        vols = [
            float(p.get("volatility", 0.20))
            for p in positions
        ]
        portfolio_volatility = sum(
            w * v for w, v in zip(weights, vols)
        )
        concentration = sum(w * w for w in weights)
        if portfolio_volatility <= 0.15:
            level = "LOW"
        elif portfolio_volatility <= 0.25:
            level = "MEDIUM"
        elif portfolio_volatility <= 0.35:
            level = "HIGH"
        else:
            level = "VERY_HIGH"
        return {
            "portfolio_volatility": round(portfolio_volatility, 4),
            "concentration": round(concentration, 4),
            "risk_level": level,
        }
