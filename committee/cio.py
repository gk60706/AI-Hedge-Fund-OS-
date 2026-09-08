"""V1.0 CIO 基金经理 Agent：根据研究委员会评分给出投资决策。"""


class CIOAgent:
    def decide(self, research):
        score = research["research_score"]
        if score >= 80:
            action = "BUY"
            position = 0.2
        elif score >= 60:
            action = "WATCH"
            position = 0.05
        else:
            action = "PASS"
            position = 0
        return {
            "decision": action,
            "position": position,
            "confidence": score,
        }
