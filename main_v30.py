"""V3.0 AI Autonomous Hedge Fund 主程序（第一个闭环版本）。

运行：python main_v30.py
"""
from __future__ import annotations

from agents.investment_committee import InvestmentCommitteeV29 as InvestmentCommittee
from portfolio.portfolio import PortfolioV30 as Portfolio
from portfolio.portfolio_manager import PortfolioManagerV30 as PortfolioManager
from risk.risk_engine import RiskEngineV30 as RiskEngine
from trading.paper_broker import PaperBrokerV30 as PaperBroker
from trading.execution_engine import ExecutionEngineV30 as ExecutionEngine
from scanner.stock_scanner import StockScannerV30 as StockScanner


def main():
    print()
    print(
        "=" * 70
    )
    print(
        "AI HEDGE FUND OS V3.0"
    )
    print(
        "=" * 70
    )
    # =========================================================
    # 1. 市场候选股票
    # =========================================================
    stocks = [

        {
            "code": "300394",
            "name": "天孚通信",
            "latest_price": 100,
            "change_pct": 2.5,
            "pe_dynamic": 35,
            "pb": 5,
            "market_cap": 1e11,
            "turnover_pct": 3,
        },

        {
            "code": "688568",
            "name": "中科星图",
            "latest_price": 80,
            "change_pct": 1.2,
            "pe_dynamic": 40,
            "pb": 4,
            "market_cap": 5e10,
            "turnover_pct": 2,
        },
    ]
    scanner = StockScanner()
    candidates = scanner.scan(
        stocks,
        limit=100,
    )
    print(
        "\n候选股票:",
        len(candidates),
    )
    # =========================================================
    # 2. 投资委员会
    # =========================================================
    committee = (
        InvestmentCommittee()
    )
    decisions = []
    for stock in candidates:
        code = stock["code"]
        context = {
            "market_data": stock,
            "quant_signal": {
                "score": 78,
                "reasons": [
                    "动量因子强",
                    "资金因子改善",
                ],
            },
            "macro": {
                "score": 65,
                "regime": "NEUTRAL_BULLISH",
            },
            "risk": {
                "max_drawdown": -0.12,
                "volatility": 0.028,
            },
        }
        result = (
            committee.deliberate(
                context
            )
        )
        decision = result["committee"]
        decisions.append({
            "code": code,
            "name": stock["name"],
            "decision": decision["decision"],
            "weighted_score": decision["weighted_score"],
        })
    # =========================================================
    # 3. Portfolio Manager
    # =========================================================
    portfolio_manager = (
        PortfolioManager(
            max_positions=10,
            max_single_weight=0.20,
        )
    )
    targets = (
        portfolio_manager.build_targets(
            decisions
        )
    )
    print(
        "\n===== 投资组合 ====="
    )
    for target in targets:
        print(
            target["code"],
            "weight=",
            round(
                target["target_weight"]
                * 100,
                2,
            ),
            "%",
            "score=",
            target["score"],
        )
    # =========================================================
    # 4. Risk Engine
    # =========================================================
    risk_engine = RiskEngine()
    weights = {
        target["code"]:
        target["target_weight"]
        for target in targets
    }
    risk_result = (
        risk_engine.validate_portfolio(
            weights
        )
    )
    print(
        "\n风险检查:",
        risk_result,
    )
    if not risk_result["allowed"]:
        print("风险检查失败，停止交易。")
        return
    # =========================================================
    # 5. 创建模拟账户
    # =========================================================
    portfolio = Portfolio(
        initial_cash=1_000_000
    )
    broker = PaperBroker(
        portfolio=portfolio
    )
    execution = ExecutionEngine(
        broker
    )
    prices = {
        stock["code"]: stock["latest_price"]
        for stock in candidates
    }
    names = {
        stock["code"]: stock["name"]
        for stock in candidates
    }
    # =========================================================
    # 6. 模拟交易
    # =========================================================
    orders = (
        execution.execute_targets(
            targets=targets,
            prices=prices,
            names=names,
        )
    )
    print(
        "\n===== 交易结果 ====="
    )
    for order in orders:
        print(
            order.code,
            order.side.value,
            order.quantity,
            order.price,
            order.status,
        )
    # =========================================================
    # 7. Portfolio Snapshot
    # =========================================================
    print(
        "\n===== Portfolio ====="
    )
    snapshot = (
        portfolio.snapshot()
    )
    print(
        "Cash:",
        snapshot["cash"],
    )
    print(
        "Market Value:",
        snapshot["market_value"],
    )
    print(
        "Total Value:",
        snapshot["total_value"],
    )
    print(
        "Return:",
        round(
            snapshot["return_pct"]
            * 100,
            2,
        ),
        "%",
    )
    print(
        "\n===== V3.0 COMPLETE ====="
    )


if __name__ == "__main__":
    main()
