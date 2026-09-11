"""V1.4 5000 股票扫描器：用投资经理团队对每只股票求平均分。

V2.2 追加：StockScannerV22（A股股票扫描 Agent，动量/量能/资金流因子打分）。
"""


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


# ---------------------------------------------------------------------------
# V2.2 A股股票扫描 Agent：扫描 5000 只股票寻找强趋势、资金流入、AI 热点。
# ---------------------------------------------------------------------------
class StockScannerV22:
    """V2.2 因子扫描器：按动量/量能/资金流打分（>=70 入选）。"""

    def __init__(self, market_data):
        self.data = market_data

    def scan(self) -> list:
        """扫描并返回按分数降序的候选股列表。

        Returns:
            [{"code": str, "score": int}, ...]
        """
        candidates = []
        for stock in self.data:
            score = 0
            if stock["momentum"] > 0:
                score += 30
            if stock["volume_ratio"] > 1.5:
                score += 30
            if stock["fund_flow"] > 0:
                score += 40
            if score >= 70:
                candidates.append(
                    {
                        "code": stock["code"],
                        "score": score,
                    }
                )
        return sorted(candidates, key=lambda x: x["score"], reverse=True)
