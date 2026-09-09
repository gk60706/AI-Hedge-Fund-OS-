"""V1.3 投资经理基础类：所有投资风格 Agent 的抽象基类。"""


class InvestmentManager:
    """投资经理基类。子类必须实现 analyze()。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def analyze(self, market) -> dict:
        raise NotImplementedError
