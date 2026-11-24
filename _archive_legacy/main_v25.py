"""V2.5 量化交易风控中心：交易审批流程（Risk Agent → Risk Committee）。"""

from risk_committee.risk_agent import RiskAgent
from risk_committee.risk_vote import RiskCommittee

trade = {"code": "300394", "position": 0.1}
market = {"volatility": 0.2}

agent = RiskAgent()
committee = RiskCommittee()

opinion = agent.review(trade, market)
decision = committee.vote([opinion, "APPROVE", "APPROVE"])
print("风险委员会结果:", decision)
