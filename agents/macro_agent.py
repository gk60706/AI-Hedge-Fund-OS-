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


# ---------------------------------------------------------------------------
# V2.0 宏观 Agent（多智能体基金经理系统）：analyze() 无参，输出宏观环境判断。
# 与 V1.3 MacroAgent（analyze(data)）并存，故以 MacroAgentV20 命名。
# ---------------------------------------------------------------------------
class MacroAgentV20:
    """V2.0 宏观环境 Agent。"""

    def analyze(self) -> dict:
        """输出宏观判断（研究/模拟占位，无真实数据时保持中性）。"""
        return {
            "market": "NEUTRAL",
            "risk": "MEDIUM",
            "comment": "等待政策方向确认",
        }
