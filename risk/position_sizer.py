"""V1.7 仓位管理：按 AI 置信度计算仓位。"""


class PositionSizer:
    """仓位管理器。"""

    def calculate(self, confidence: float, max_position: float = 0.20) -> float:
        confidence = max(0.0, min(confidence, 1.0))
        position = confidence * max_position
        return round(position, 4)
