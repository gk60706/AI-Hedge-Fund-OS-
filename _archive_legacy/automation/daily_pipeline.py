"""V2.2 核心自动流水线：市场扫描 → 发现机会 → 委员会决策。"""


class DailyPipeline:
    """每日自动投资研究流水线。"""

    def __init__(self, scanner, committee):
        self.scanner = scanner
        self.committee = committee

    def run(self) -> dict:
        """执行一轮每日研究。

        Returns:
            {"stocks": [...], "decision": str}
        """
        print("开始AI基金每日研究")
        stocks = self.scanner.scan()
        print("发现机会:", len(stocks))
        opinions = ["BUY", "BUY", "HOLD", "BUY", "BUY"]
        decision = (
            self.committee.vote(opinions)
        )
        return {"stocks": stocks, "decision": decision}
