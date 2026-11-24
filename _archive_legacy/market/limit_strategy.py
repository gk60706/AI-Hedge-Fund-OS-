"""V1.5 涨停板策略 Agent：检测接近涨停个股。"""


class LimitUpAgent:
    """涨停板检测 Agent。"""

    def check(self, price: float, yesterday: float) -> dict:
        change = (price / yesterday - 1) * 100
        if change >= 9.8:
            return {
                "signal": "LIMIT_UP",
                "score": 100,
            }
        return {
            "signal": "NORMAL",
            "score": 50,
        }
