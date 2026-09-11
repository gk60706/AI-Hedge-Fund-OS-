"""V2.3 五档盘口分析 Agent：买卖盘堆量判断主力吸筹。"""


class OrderBookAnalyzer:
    """五档盘口分析。"""

    def analyze(self, orderbook: dict) -> dict:
        """分析买卖盘比例。

        Args:
            orderbook: {"bid": [...], "ask": [...]}。

        Returns:
            {"signal": "MAIN_FORCE_BUY" | "NORMAL"}
        """
        buy = sum(orderbook["bid"])
        sell = sum(orderbook["ask"])
        ratio = (buy / (sell + 1))
        if ratio > 2:
            return {"signal": "MAIN_FORCE_BUY"}
        return {"signal": "NORMAL"}
