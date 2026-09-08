"""V1.0 新闻 Agent：基于关键词的舆情分析评分。"""
from core.agent import BaseAgent


class NewsAgent(BaseAgent):
    def run(self, stock):
        news = stock.get("news", "")
        score = 50
        positive = ["订单", "增长", "合作"]
        for x in positive:
            if x in news:
                score += 10
        return {
            "agent": self.name,
            "score": min(score, 100),
            "reason": "舆情分析",
        }
