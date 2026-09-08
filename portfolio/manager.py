"""V1.0 AI 自动调仓：按 CIO 决策构建组合。"""


class PortfolioManager:
    def allocate(self, decisions):
        portfolio = []
        for d in decisions:
            if d["decision"] == "BUY":
                portfolio.append({
                    "code": d["code"],
                    "weight": d["position"],
                })
        return portfolio
