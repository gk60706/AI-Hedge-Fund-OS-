"""V1.0 基本面 Agent：基于 ROE 与成长性的盈利质量评分。"""
from core.agent import BaseAgent


class FundamentalAgent(BaseAgent):
    def run(self, stock):
        score = 50
        if stock.get("roe", 0) > 15:
            score += 25
        if stock.get("growth", 0) > 20:
            score += 20
        return {
            "agent": self.name,
            "score": score,
            "reason": "盈利能力分析",
        }
