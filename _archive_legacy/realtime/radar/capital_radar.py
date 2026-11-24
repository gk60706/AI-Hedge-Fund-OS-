"""V2.3 主力资金雷达 Agent：放量上涨 / 大单流入 / 主动买入 / 价格突破。"""


class CapitalRadar:
    """主力资金雷达。"""

    def analyze(self, data: dict) -> dict:
        """打分识别主力吸筹。

        Args:
            data: {"volume_ratio", "buy_amount", "sell_amount", "price_change"}。

        Returns:
            {"capital_score": int, "signal": "ACCUMULATION" | "WAIT"}
        """
        score = 0
        if data["volume_ratio"] > 2:
            score += 30
        if data["buy_amount"] > data["sell_amount"]:
            score += 40
        if data["price_change"] > 0:
            score += 30
        return {
            "capital_score": score,
            "signal": "ACCUMULATION" if score >= 70 else "WAIT",
        }
