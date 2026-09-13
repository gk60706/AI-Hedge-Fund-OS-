"""V3.1 AI Portfolio Manager 主程序。

用法：python main_v31.py
"""
from __future__ import annotations

from portfolio.portfolio_manager import PortfolioManagerV31 as PortfolioManager
from risk.portfolio_risk import PortfolioRisk


def main():
    print()
    print("=" * 70)
    print("AI HEDGE FUND OS V3.1")
    print("AI PORTFOLIO MANAGER")
    print("=" * 70)

    candidates = [
        {
            "code": "300394",
            "name": "天孚通信",
            "industry": "光通信",
            "fundamental_score": 88,
            "valuation_score": 60,
            "trend_score": 82,
            "capital_score": 85,
            "industry_score": 90,
            "risk_score": 70,
            "volatility": 0.35,
        },
        {
            "code": "688568",
            "name": "中科星图",
            "industry": "卫星互联网",
            "fundamental_score": 80,
            "valuation_score": 55,
            "trend_score": 75,
            "capital_score": 70,
            "industry_score": 82,
            "risk_score": 72,
            "volatility": 0.30,
        },
        {
            "code": "300750",
            "name": "宁德时代",
            "industry": "新能源",
            "fundamental_score": 85,
            "valuation_score": 72,
            "trend_score": 65,
            "capital_score": 68,
            "industry_score": 70,
            "risk_score": 80,
            "volatility": 0.25,
        },
        {
            "code": "600519",
            "name": "贵州茅台",
            "industry": "消费",
            "fundamental_score": 92,
            "valuation_score": 60,
            "trend_score": 55,
            "capital_score": 60,
            "industry_score": 65,
            "risk_score": 90,
            "volatility": 0.20,
        },
        {
            "code": "601318",
            "name": "中国平安",
            "industry": "金融",
            "fundamental_score": 78,
            "valuation_score": 80,
            "trend_score": 60,
            "capital_score": 65,
            "industry_score": 68,
            "risk_score": 88,
            "volatility": 0.18,
        },
    ]

    manager = PortfolioManager(
        max_positions=5,
        max_single_weight=0.20,
    )
    result = manager.build_portfolio(candidates)
    print("\n===== FINAL PORTFOLIO =====")
    for position in result["positions"]:
        print(
            position["code"],
            position["name"],
            "Alpha=",
            position["alpha_score"],
            "Weight=",
            f"{position['weight'] * 100:.2f}%",
            "Vol=",
            f"{position['volatility'] * 100:.2f}%",
        )
    print("\n===== CONSTRAINT CHECK =====")
    print(result["validation"])

    risk = PortfolioRisk()
    risk_result = risk.analyze(result["positions"])
    print("\n===== PORTFOLIO RISK =====")
    print(risk_result)

    print("\n===== V3.1 COMPLETE =====")


if __name__ == "__main__":
    main()
