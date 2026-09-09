"""V1.3 资金分配器：按策略得分加权分配资金（模拟组合，无实盘）。"""


class CapitalAllocator:
    """资金分配器。

    按各策略 score 占总分的比例分配资金，
    输出权重与分配金额（研究/模拟用途）。
    """

    def allocate(self, strategies: list, capital: float) -> list:
        total_score = sum(s["score"] for s in strategies)
        if total_score <= 0:
            return []
        portfolio = []
        for s in strategies:
            weight = s["score"] / total_score
            portfolio.append(
                {
                    "strategy": s["style"],
                    "weight": round(weight, 3),
                    "capital": capital * weight,
                }
            )
        return portfolio
