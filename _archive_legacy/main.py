"""AI Hedge Fund OS V1.0 主程序（MVP 正式版）。

多 Agent 研究委员会 → CIO 决策。仅研究与模拟，禁止自动实盘交易。
"""
from agents.fundamental_agent import FundamentalAgent
from agents.quant_agent import QuantAgent
from agents.news_agent import NewsAgent
from committee.research_committee import ResearchCommittee
from committee.cio import CIOAgent

agents = [
    FundamentalAgent("基本面分析师"),
    QuantAgent("量化分析师"),
    NewsAgent("新闻分析师"),
]

committee = ResearchCommittee(agents)
cio = CIOAgent()

stock = {
    "code": "300394",
    "roe": 20,
    "growth": 30,
    "alpha": 85,
    "news": "AI订单增长",
}

research = committee.analyze(stock)
decision = cio.decide(research)

print(research)
print(decision)
