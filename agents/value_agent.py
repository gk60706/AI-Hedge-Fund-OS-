"""V1.3 价值投资 Agent：低 PE + 高 ROE 打分。"""

from agents.base_manager import InvestmentManager


class ValueAgent(InvestmentManager):
    """价值投资经理：偏好低估值（PE<30）与高盈利质量（ROE>15）。"""

    def analyze(self, stock: dict) -> dict:
        score = 50
        if stock.get("pe", 100) < 30:
            score += 20
        if stock.get("roe", 0) > 15:
            score += 20
        return {
            "manager": self.name,
            "style": "VALUE",
            "score": score,
        }
