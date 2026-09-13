"""V2.9 AI 多 Agent 投资委员会：委员会编排。"""
from __future__ import annotations

from typing import Any

from agents.value_agent import ValueAgentV29
from agents.trend_agent import TrendAgentV29
from agents.quant_agent import QuantAgentV29
from agents.macro_agent import MacroAgentV29
from agents.risk_agent import RiskAgentV29
from committee.voting import CommitteeVoting


class InvestmentCommitteeV29:
    def __init__(self):
        self.agents = [
            ValueAgentV29(),
            TrendAgentV29(),
            QuantAgentV29(),
            MacroAgentV29(),
            RiskAgentV29(),
        ]
        self.voting = CommitteeVoting()

    def deliberate(self, context: dict[str, Any]) -> dict[str, Any]:
        results = {}
        for agent in self.agents:
            result = agent.analyze(context)
            results[agent.name] = result
        voting_result = self.voting.vote(results)
        return {
            "agents": results,
            "committee": voting_result,
        }
