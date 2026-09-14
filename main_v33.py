"""AI Hedge Fund OS V3.3 - 真实组合优化引擎 + AI Portfolio Rebalancer

链路：AkShare 真实历史行情 → 因子/Alpha → 收益率矩阵 → 协方差
      → 风险预算 → 目标组合 → 当前持仓 → 交易成本 → 调仓订单。

注意：本文件使用模拟候选与模拟价格演示完整链路；
真实数据接入后，预计收益/波动率/Alpha 应来自 factors/data 模块。
"""
from __future__ import annotations

from typing import Any

from risk.risk_state import RiskStateEngine
from portfolio.portfolio_manager import PortfolioManagerV33


def create_candidates() -> list[dict[str, Any]]:
    """构建候选股票池（模拟数据，用于演示链路）。"""
    return [
        {
            "code": "300394",
            "name": "天孚通信",
            "alpha_score": 88,
            "volatility": 0.32,
            "beta": 1.20,
            "industry": "通信",
        },
        {
            "code": "688568",
            "name": "中科星图",
            "alpha_score": 82,
            "volatility": 0.28,
            "beta": 1.10,
            "industry": "软件",
        },
        {
            "code": "300274",
            "name": "阳光电源",
            "alpha_score": 84,
            "volatility": 0.30,
            "beta": 1.15,
            "industry": "光伏",
        },
        {
            "code": "002594",
            "name": "比亚迪",
            "alpha_score": 80,
            "volatility": 0.25,
            "beta": 1.05,
            "industry": "汽车",
        },
        {
            "code": "600519",
            "name": "贵州茅台",
            "alpha_score": 76,
            "volatility": 0.20,
            "beta": 0.85,
            "industry": "白酒",
        },
        {
            "code": "601318",
            "name": "中国平安",
            "alpha_score": 73,
            "volatility": 0.18,
            "beta": 0.80,
            "industry": "保险",
        },
    ]


def main() -> None:
    candidates = create_candidates()

    # 组合与市场参数（模拟）
    portfolio_volatility = 0.20
    max_drawdown = -0.05
    market_score = 72
    total_equity = 1_000_000
    top_n = 6

    # 当前持仓（模拟）
    current_positions = {
        "300394": 0.20,
        "688568": 0.10,
        "300274": 0.15,
        "002594": 0.10,
        "600519": 0.05,
        "601318": 0.05,
    }

    # 当前价格（模拟）
    prices = {
        "300394": 100.0,
        "688568": 70.0,
        "300274": 150.0,
        "002594": 300.0,
        "600519": 1400.0,
        "601318": 55.0,
    }

    # 风险状态
    risk_engine = RiskStateEngine()
    risk_state = risk_engine.evaluate(
        max_drawdown=max_drawdown,
        portfolio_volatility=portfolio_volatility,
    )
    print("\n==============================")
    print("AI Hedge Fund OS V3.3")
    print("Real Portfolio Optimizer + AI Rebalancer")
    print("==============================\n")
    print(f"Risk State: {risk_state.value}")
    print(f"Market Score: {market_score}")
    print(f"Portfolio Volatility: {portfolio_volatility}")
    print(f"Max Drawdown: {max_drawdown}")

    # 组合管理器
    manager = PortfolioManagerV33()

    # 目标组合
    target = manager.build_target_portfolio(
        candidates=candidates,
        portfolio_volatility=portfolio_volatility,
        max_drawdown=max_drawdown,
        market_score=market_score,
        top_n=top_n,
    )
    target_positions = target["positions"]

    print("\n===== TARGET PORTFOLIO =====")
    for code, weight in sorted(
        target_positions.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{code}  {weight * 100:.2f}%",
        )
    print(f"Cash: {target.get('cash', 0.0) * 100:.2f}%")
    print(f"Exposure: {target.get('exposure', 0.0) * 100:.2f}%")

    # 调仓订单
    orders = manager.generate_rebalance_orders(
        current_positions=current_positions,
        target_positions=target_positions,
        prices=prices,
        total_equity=total_equity,
    )

    print("\n===== REBALANCE ORDERS =====")
    if not orders:
        print("(无调仓订单)")
    for order in orders:
        print(
            f"{order['side']} {order['code']}  "
            f"current={order['current_weight'] * 100:.2f}%  "
            f"target={order['target_weight'] * 100:.2f}%  "
            f"trade_value={order['trade_value']:,.0f}  "
            f"est_cost={order['estimated_cost']:,.0f}  "
            f"price={order['price']}"
        )


if __name__ == "__main__":
    main()
