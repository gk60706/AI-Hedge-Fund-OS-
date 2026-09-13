"""V3.2 Dynamic Risk Budget + Portfolio Optimization 主程序。

用法：python main_v32.py
"""
from __future__ import annotations

from pprint import pprint

from portfolio.portfolio_manager import PortfolioManagerV32 as PortfolioManager
from risk.risk_state import RiskStateEngine


def create_demo_candidates():
    return [
        {
            "code": "300394",
            "name": "天孚通信",
            "industry": "AI光通信",
            "alpha_score": 88,
            "volatility": 0.32,
            "beta": 1.20,
        },
        {
            "code": "688568",
            "name": "中科星图",
            "industry": "卫星应用",
            "alpha_score": 82,
            "volatility": 0.28,
            "beta": 1.10,
        },
        {
            "code": "300274",
            "name": "阳光电源",
            "industry": "新能源",
            "alpha_score": 84,
            "volatility": 0.30,
            "beta": 1.15,
        },
        {
            "code": "002594",
            "name": "比亚迪",
            "industry": "新能源",
            "alpha_score": 80,
            "volatility": 0.25,
            "beta": 1.05,
        },
        {
            "code": "600519",
            "name": "贵州茅台",
            "industry": "消费",
            "alpha_score": 76,
            "volatility": 0.20,
            "beta": 0.85,
        },
        {
            "code": "601318",
            "name": "中国平安",
            "industry": "金融",
            "alpha_score": 73,
            "volatility": 0.18,
            "beta": 0.80,
        },
    ]


def main():
    candidates = create_demo_candidates()
    # 当前组合状态
    portfolio_volatility = 0.22
    max_drawdown = -0.06
    market_score = 72

    # -------------------------------
    # 风险状态
    # -------------------------------
    risk_engine = RiskStateEngine()
    risk_state = risk_engine.evaluate(
        max_drawdown=max_drawdown,
        portfolio_volatility=portfolio_volatility,
    )
    print("\n==============================")
    print("AI Hedge Fund OS V3.2")
    print("==============================")
    print("Risk State:", risk_state.value)

    # -------------------------------
    # Portfolio Manager
    # -------------------------------
    manager = PortfolioManager()
    portfolio = manager.build_portfolio(
        candidates=candidates,
        portfolio_volatility=portfolio_volatility,
        max_drawdown=max_drawdown,
        market_score=market_score,
        top_n=6,
    )
    print("\n===== Portfolio =====")
    pprint(portfolio)
    print("\n===== Positions =====")
    for code, weight in portfolio["positions"].items():
        print(code, f"{weight * 100:.2f}%")
    print("\nCash:", f"{portfolio['cash'] * 100:.2f}%")
    print("Exposure:", f"{portfolio['exposure'] * 100:.2f}%")


if __name__ == "__main__":
    main()
