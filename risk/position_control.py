"""V2.4 动态仓位控制：评分90+ → 20%，80+ → 10%，70 → 5%。"""


class PositionControl:
    """按评分计算目标仓位。"""

    def calculate(self, score):
        if score >= 90:
            return 0.2
        elif score >= 80:
            return 0.1
        elif score >= 70:
            return 0.05
        return 0
