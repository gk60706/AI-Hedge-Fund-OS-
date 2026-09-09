"""V1.5 Level-5 五档盘口分析：买卖压力强度。"""


class OrderBookAnalyzer:
    """五档盘口分析器。"""

    def analyze(self, data: dict) -> dict:
        buy_volume = sum(
            [
                data["bid1_volume"],
                data["bid2_volume"],
                data["bid3_volume"],
                data["bid4_volume"],
                data["bid5_volume"],
            ]
        )
        sell_volume = sum(
            [
                data["ask1_volume"],
                data["ask2_volume"],
                data["ask3_volume"],
                data["ask4_volume"],
                data["ask5_volume"],
            ]
        )
        strength = buy_volume / (sell_volume + 1)
        if strength > 2:
            signal = "BUY_PRESSURE"
        elif strength < 0.5:
            signal = "SELL_PRESSURE"
        else:
            signal = "BALANCE"
        return {
            "strength": strength,
            "signal": signal,
        }
