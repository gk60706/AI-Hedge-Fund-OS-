"""V1.3 宏观 Agent：利率与流动性环境打分。"""


class MacroAgent:
    """宏观策略经理：宽松利率 + 高流动性加分。"""

    def analyze(self, data: dict) -> dict:
        score = 50
        if data["rate"] == "DOWN":
            score += 20
        if data["liquidity"] == "HIGH":
            score += 20
        return {
            "style": "MACRO",
            "score": score,
        }
