"""V3.1 Alpha 评分：基于个股多维评分的 Alpha 分数。"""

from __future__ import annotations

from typing import Any


class AlphaScore:
    """根据股票的多维评分（基本面/估值/趋势/资金/行业/风险）计算 Alpha 分数。

    Alpha = fundamental*0.30 + valuation*0.15 + trend*0.20
            + capital*0.15 + industry*0.10 + (100-risk)*0.10
    分数范围 0-100。
    """

    WEIGHTS = {
        "fundamental": 0.30,
        "valuation": 0.15,
        "trend": 0.20,
        "capital": 0.15,
        "industry": 0.10,
        "risk_bonus": 0.10,
    }

    def calculate(self, stock: dict[str, Any]) -> float:
        """Args:
            stock: 含 fundamental_score / valuation_score / trend_score /
                   capital_score / industry_score / risk_score 的股票信息。

        Returns:
            Alpha 分数（0-100，保留两位小数）。
        """
        fundamental = float(stock.get("fundamental_score", 0))
        valuation = float(stock.get("valuation_score", 0))
        trend = float(stock.get("trend_score", 0))
        capital = float(stock.get("capital_score", 0))
        industry = float(stock.get("industry_score", 0))
        risk = float(stock.get("risk_score", 100))
        risk_bonus = max(0.0, 100.0 - risk)

        alpha = (
            fundamental * self.WEIGHTS["fundamental"]
            + valuation * self.WEIGHTS["valuation"]
            + trend * self.WEIGHTS["trend"]
            + capital * self.WEIGHTS["capital"]
            + industry * self.WEIGHTS["industry"]
            + risk_bonus * self.WEIGHTS["risk_bonus"]
        )
        return round(max(0.0, min(100.0, alpha)), 2)
