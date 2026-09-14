"""AI Hedge Fund OS V3.4 - 机构级 Ensemble Portfolio Optimizer

链路：Mean-Variance + Risk Parity + Black-Litterman + Alpha
      → Ensemble → Risk Constraints → Target Portfolio
      → 流动性/换手约束 → 整数手仓位。

注意：本文件的 expected_returns / alpha_scores / correlation
仍是示例数据，不要把输出仓位直接用于真实交易。
"""
from __future__ import annotations

import numpy as np

from optimization.ensemble import EnsembleOptimizer
from portfolio.optimizer import InstitutionalPortfolioOptimizer
from portfolio.institutional_manager import InstitutionalPortfolioManager


def main() -> None:
    codes = [
        "300394",
        "688568",
        "300274",
        "002594",
        "600519",
        "601318",
    ]
    names = {
        "300394": "天孚通信",
        "688568": "中科星图",
        "300274": "阳光电源",
        "002594": "比亚迪",
        "600519": "贵州茅台",
        "601318": "中国平安",
    }

    # -----------------------------
    # 模拟预期收益
    # -----------------------------
    expected_returns = np.array(
        [0.18, 0.14, 0.16, 0.13, 0.10, 0.09],
    )

    # -----------------------------
    # Alpha
    # -----------------------------
    alpha_scores = {
        "300394": 88,
        "688568": 82,
        "300274": 84,
        "002594": 80,
        "600519": 76,
        "601318": 73,
    }

    # -----------------------------
    # 模拟协方差
    # -----------------------------
    volatility = np.array(
        [0.32, 0.28, 0.30, 0.25, 0.20, 0.18],
    )
    correlation = np.array(
        [
            [1.00, 0.45, 0.50, 0.40, 0.20, 0.15],
            [0.45, 1.00, 0.35, 0.30, 0.15, 0.10],
            [0.50, 0.35, 1.00, 0.55, 0.20, 0.15],
            [0.40, 0.30, 0.55, 1.00, 0.25, 0.20],
            [0.20, 0.15, 0.20, 0.25, 1.00, 0.35],
            [0.15, 0.10, 0.15, 0.20, 0.35, 1.00],
        ],
    )
    covariance = (
        np.diag(volatility)
        @ correlation
        @ np.diag(volatility)
    )

    # -----------------------------
    # Optimizer
    # -----------------------------
    optimizer = InstitutionalPortfolioOptimizer()
    target_weights = optimizer.optimize(
        codes=codes,
        covariance=covariance,
        expected_returns=expected_returns,
        alpha_scores=alpha_scores,
    )

    print("\n==============================")
    print("AI Hedge Fund OS V3.4")
    print("Institutional Portfolio Optimizer")
    print("==============================\n")

    print("===== TARGET WEIGHTS =====")
    for code, weight in sorted(
        target_weights.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(
            f"{names.get(code, code)} {code}  {weight * 100:.2f}%",
        )

    # -----------------------------
    # Position sizing
    # -----------------------------
    prices = {
        "300394": 100,
        "688568": 70,
        "300274": 150,
        "002594": 300,
        "600519": 1400,
        "601318": 55,
    }
    total_equity = 1_000_000
    manager = InstitutionalPortfolioManager()
    positions = manager.size_positions(
        weights=target_weights,
        prices=prices,
        total_equity=total_equity,
    )

    print("\n===== POSITION SIZING =====")
    for code, position in positions.items():
        print(
            f"{names.get(code, code)}  "
            f"shares={position['shares']}  "
            f"value={round(position['value'], 2)}  "
            f"weight={position['actual_weight'] * 100:.2f}%",
        )


if __name__ == "__main__":
    main()
