"""V1.5 主力资金雷达：识别大单（>50 万）买卖方向并评分。"""


class MainForceDetector:
    """主力资金检测器。"""

    def detect(self, ticks: list) -> dict:
        buy = 0
        sell = 0
        for tick in ticks:
            if tick["amount"] > 500000:
                if tick["side"] == "BUY":
                    buy += tick["amount"]
                else:
                    sell += tick["amount"]
        ratio = buy / (sell + 1)
        score = min(ratio * 50, 100)
        return {"main_force_score": score}
