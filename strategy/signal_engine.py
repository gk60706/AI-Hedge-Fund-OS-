"""V2.4 AI 交易信号引擎。"""


class SignalEngine:
    """AI 交易信号：资金评分 + 风险等级 → BUY / WAIT。"""

    def generate(self, analysis):
        if (analysis["capital"] > 70 and analysis["risk"] == "LOW"):
            return "BUY"
        return "WAIT"
