"""V1.0 AI 研究委员会：聚合多个 Agent 的研究结论并计算综合评分。"""


class ResearchCommittee:
    def __init__(self, agents):
        self.agents = agents

    def analyze(self, stock):
        results = []
        for agent in self.agents:
            result = agent.run(stock)
            results.append(result)
        score = sum(x["score"] for x in results) / len(results)
        return {
            "research_score": score,
            "detail": results,
        }
