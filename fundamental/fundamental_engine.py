"""V0.4 基本面综合引擎：聚合五大基本面 Agent。"""
from __future__ import annotations

from agents.models import AgentResult
from fundamental.financial_agent import financial_agent
from fundamental.industry_agent import industry_agent
from fundamental.moat_agent import moat_agent
from fundamental.news_agent import news_agent
from fundamental.valuation_agent import valuation_agent


def run_fundamental_analysis(
    financial: dict,
    news: str,
    industry: str,
    company: str,
) -> dict:
    agents: list[AgentResult] = [
        financial_agent(financial),
        news_agent(news),
        industry_agent(industry),
        moat_agent(company),
        valuation_agent(financial),
    ]
    score = sum(x.score for x in agents) / len(agents)
    return {
        "fundamental_score": score,
        "agents": agents,
    }
