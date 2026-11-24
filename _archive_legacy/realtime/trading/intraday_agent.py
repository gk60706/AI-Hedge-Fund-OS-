"""V2.3 盘中交易 Agent：根据资金雷达 + 盘口信号决定买/卖/等待。"""


class IntradayTrader:
    """盘中 AI 交易 Agent。"""

    def decide(self, radar: dict, orderbook: dict) -> dict:
        """决策。

        Args:
            radar: CapitalRadar.analyze() 输出。
            orderbook: OrderBookAnalyzer.analyze() 输出。

        Returns:
            {"action": "BUY", "position": 0.1} 或 {"action": "WAIT"}
        """
        if (radar["capital_score"] >= 70 and orderbook["signal"] == "MAIN_FORCE_BUY"):
            return {"action": "BUY", "position": 0.1}
        return {"action": "WAIT"}
