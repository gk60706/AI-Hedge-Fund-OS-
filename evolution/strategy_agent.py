"""V1.2 AI 策略生成 Agent：根据 Alpha 因子生成策略描述。"""


class StrategyAgent:
    """策略生成 Agent。

    将 Alpha 因子转换为结构化策略：
    entry 条件、exit 条件与仓位。
    """

    def create(self, alpha: dict) -> dict:
        """根据 Alpha 因子创建策略。

        :param alpha: ``{"factor": str, "formula": str}``
        :return: ``{"name", "entry", "exit", "position"}``
        """
        strategy = {
            "name": "AI_" + alpha["factor"],
            "entry": alpha["formula"] + ">0",
            "exit": "drawdown>8%",
            "position": 0.2,
        }
        return strategy
