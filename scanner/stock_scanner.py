"""V1.4 5000 股票扫描器：用投资经理团队对每只股票求平均分。"""


class StockScanner:
    """股票扫描器：聚合多个投资经理的分析分数。"""

    def __init__(self, agents: list) -> None:
        self.agents = agents

    def scan(self, stocks: list) -> list:
        results = []
        for stock in stocks:
            score = 0
            for agent in self.agents:
                result = agent.analyze(stock)
                score += result["score"]
            if self.agents:
                score /= len(self.agents)
            results.append(
                {
                    "code": stock["code"],
                    "score": score,
                }
            )
        return sorted(results, key=lambda x: x["score"], reverse=True)
