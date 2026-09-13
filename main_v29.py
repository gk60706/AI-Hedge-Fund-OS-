"""V2.9 AI 多 Agent 投资委员会主程序。

运行：python main_v29.py
"""
from __future__ import annotations

from agents.investment_committee import InvestmentCommitteeV29 as InvestmentCommittee
from committee.allocator import PositionAllocator
from committee.decision import InvestmentDecision


def main():
    stock_code = "300394"
    market_data = {
        "code": stock_code,
        "name": "示例股票",
        "latest_price": 100.0,
        "change_pct": 2.35,
        "pe_dynamic": 35.0,
        "pb": 5.2,
    }
    context = {
        "market_data": market_data,
        "quant_signal": {
            "score": 78,
            "reasons": [
                "动量因子较强",
                "资金因子改善",
                "成交量结构正常",
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
    committee = (
        InvestmentCommittee()
    )
    result = committee.deliberate(context)
    risk_score = result["agents"]["risk_agent"]["score"]
    allocator = PositionAllocator()
    allocation = allocator.allocate(
        decision=result["committee"]["decision"],
        risk_score=risk_score,
        portfolio_value=1_000_000,
        max_position=0.20,
    )
    decision_builder = (
        InvestmentDecision()
    )
    final_decision = (
        decision_builder.build(
            stock_code,
            result,
            allocation,
        )
    )
    print(
        "\n"
    )
    print(
        "=" * 60
    )
    print(
        "AI HEDGE FUND OS V2.9"
    )
    print(
        "=" * 60
    )
    print(
        "\n股票:",
        stock_code,
    )
    print(
        "\n投资委员会决策:",
        final_decision["decision"],
    )
    print(
        "委员会评分:",
        final_decision["weighted_score"],
    )
    print(
        "目标仓位:",
        final_decision["position_ratio"],
    )
    print(
        "目标金额:",
        final_decision["position_value"],
    )
    print(
        "\n===== Agent 投票 ====="
    )
    for name, vote in (
        final_decision["votes"].items()
    ):
        print(
            name,
            "=>",
            vote["signal"],
            "weight=",
            vote["weight"],
        )
    print(
        "\n===== Agent 分析 ====="
    )
    for name, analysis in (
        final_decision["agent_analysis"].items()
    ):
        print(
            name,
            "score=",
            analysis["score"],
            "signal=",
            analysis["signal"],
        )


if __name__ == "__main__":
    main()
